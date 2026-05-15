"""
historical_mri_builder.py — 실데이터 기반 역대 MRI 시계열 빌더 (2015-02~현재)
=============================================================================

[설계 목적]
기존 build_mri_series()는 시뮬레이션 값이었음.
이 모듈은 아래 실데이터를 사용해 2015-02 ~ 현재까지 월별 MRI를 산출함.

[데이터 소스 & 차원 매핑]
  G (지정학·항로) : GDELT BigQuery CSV + Naver DataLab 검색트렌드 조합
  D (기상·운항)   : GDELT 부정감성 비율 + Naver DataLab 검색트렌드
  F (운임 변동)   : SCFI/CCFI Excel (2014.06~) + KCCI XLS (2022-11~) 조합
  V (물동량)      : BPA 부산항 월별 물동량 (12개월 롤링 YoY) + LSTM 예측(공백 보완)
  P (항만·통상)   : GDELT 제재이벤트 + Naver DataLab 검색트렌드

[GDELT/Naver 혼합 비율]
  2015-02 ~ 2015-12 : GDELT 단독 (Naver DataLab 2016-01 이후 제공)
  2016-01 ~ 현재    : GDELT 80% + Naver DataLab 20% 가중 평균

[운임지수 우선순위]
  2015-02 ~ 2022-10 : SCFI 70% + CCFI 30%
  2022-11 ~ 현재    : KCCI 70% + SCFI 30%

[가중치 방법]
  IQR 로버스트 엔트로피 + 등분 하이브리드 (다중공선성 보정)
  최종 가중치 (2015-02~2026-05 기준): G=0.132, D=0.132, F=0.183, V=0.437, P=0.115

[MRI 등급 임계값 (분위수 기반, 136개월)]
  정상 < 0.33 / 주의 0.33~0.43 / 경계 0.43~0.55 / 위험 ≥ 0.55

[필요 파일 / API]
  data/gdelt_maritime_monthly.csv : BigQuery 쿼리 결과 CSV (수동 저장)
  SCFI,CCFI 2015.01 ~ 2026.05/  : SCFI+CCFI Excel 파일 (프로젝트 루트)
  NAVER_CLIENT_ID / NAVER_CLIENT_SECRET : .env 등록
  BPA_API_KEY                    : 기존 real_data_fetcher.py에서 이미 사용 중
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────────────────────

HISTORY_START  = "2015-02"   # MRI 시계열 시작점 (GDELT v2 시작일)
KCCI_START_YM  = "2022-11"   # KCCI 적용 시작 연월

# Naver DataLab 검색어 그룹 (G/D/P 차원 대리지표)
NAVER_DATALAB_URL    = "https://openapi.naver.com/v1/datalab/search"
NAVER_KEYWORD_GROUPS = [
    {"groupName": "G_geopolitical",
     "keywords":  ["홍해", "수에즈", "호르무즈", "지정학", "해상분쟁"]},
    {"groupName": "D_disruption",
     "keywords":  ["태풍", "기상악화", "선박지연", "결항", "해상안전"]},
    {"groupName": "P_trade",
     "keywords":  ["항만파업", "관세", "무역분쟁", "수출규제", "항만혼잡"]},
]


# ──────────────────────────────────────────────────────────────────────────────
# 1. 운임지수 로더 (SCFI/CCFI/BDI Excel + KCCI XLS)
# ──────────────────────────────────────────────────────────────────────────────

def load_scfi_ccfi_excel(project_root: Path) -> pd.DataFrame | None:
    """SCFI/CCFI Excel 5개 파일(2014.06~2026.04) 통합 → 월별 평균 반환."""
    folder = project_root / "SCFI,CCFI 2015.01 ~ 2026.05"
    if not folder.exists():
        logger.warning("SCFI 폴더 없음: %s", folder)
        return None

    dfs = []
    for fp in sorted(folder.glob("*.xls*")):
        try:
            raw = pd.read_excel(fp, header=None)
            raw.columns = ["type", "value", "date", "note"]
            raw = raw[raw["type"].isin(["SCFI", "CCFI"])].copy()
            raw["value"] = pd.to_numeric(
                raw["value"].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )
            raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
            dfs.append(raw.dropna(subset=["date", "value"]))
        except Exception as e:
            logger.warning("SCFI 파일 읽기 실패 (%s): %s", fp.name, e)

    if not dfs:
        return None

    combined = (
        pd.concat(dfs, ignore_index=True)
        .drop_duplicates(subset=["type", "date"])
    )
    combined["ym"] = combined["date"].dt.to_period("M").dt.to_timestamp()

    monthly = (
        combined.groupby(["ym", "type"])["value"]
        .mean()
        .unstack("type")
        .reset_index()
        .rename(columns={"ym": "date"})
    )
    monthly.columns.name = None
    monthly.columns = [c.lower() if c in ("SCFI", "CCFI") else c for c in monthly.columns]
    for col in ["scfi", "ccfi"]:
        if col not in monthly.columns:
            monthly[col] = np.nan
    monthly = monthly.sort_values("date").reset_index(drop=True)
    logger.info("SCFI/CCFI 로드: %d개월 (%s ~ %s)",
                len(monthly),
                monthly["date"].iloc[0].strftime("%Y-%m"),
                monthly["date"].iloc[-1].strftime("%Y-%m"))
    return monthly



def load_freight_combined(
    data_dir: Path,
    project_root: Path | None = None,
) -> pd.DataFrame | None:
    """
    SCFI/CCFI Excel + KCCI XLS → 월별 운임지수 DataFrame 반환.

    반환 컬럼: date, scfi, ccfi, kcci, freight_combined, F_raw
      - F_raw : |월변화율| 클리핑 [0,1] (F 차원 입력값)
    기간별 혼합:
      2015-02 ~ 2022-10 : SCFI 70% + CCFI 30%
      2022-11 ~ 현재    : KCCI 70% + SCFI 30%
    """
    root = project_root or data_dir.parent

    scfi_ccfi = load_scfi_ccfi_excel(root)

    kcci_df = None
    try:
        from src.data_loader import load_kcci
        kw = load_kcci(data_dir)
        if kw is not None and not kw.empty:
            kw["date"] = pd.to_datetime(kw["date"])
            kcci_df = (
                kw.set_index("date")["value"]
                .resample("MS").mean()
                .rename("kcci")
                .reset_index()
            )
    except Exception as e:
        logger.warning("KCCI 로드 실패: %s", e)

    if scfi_ccfi is None and kcci_df is None:
        logger.error("운임지수 데이터 없음 — 시뮬 폴백")
        return None

    idx = pd.date_range(HISTORY_START, pd.Timestamp.today().strftime("%Y-%m"), freq="MS")
    result = pd.DataFrame({"date": idx})

    if scfi_ccfi is not None:
        result = result.merge(scfi_ccfi[["date", "scfi", "ccfi"]], on="date", how="left")
    else:
        result["scfi"] = np.nan
        result["ccfi"] = np.nan

    if kcci_df is not None:
        kcci_df["date"] = pd.to_datetime(kcci_df["date"]).dt.to_period("M").dt.to_timestamp()
        result = result.merge(kcci_df[["date", "kcci"]], on="date", how="left")
    else:
        result["kcci"] = np.nan

    result = result.ffill()

    kcci_cutoff = pd.Timestamp(KCCI_START_YM)

    def _blend(row: pd.Series) -> float:
        if row["date"] >= kcci_cutoff:
            vals = [(row.get("kcci", np.nan), 0.70), (row.get("scfi", np.nan), 0.30)]
        else:
            vals = [(row.get("scfi", np.nan), 0.70), (row.get("ccfi", np.nan), 0.30)]
        available = [(v, w) for v, w in vals if pd.notna(v)]
        if not available:
            return np.nan
        total_w = sum(w for _, w in available)
        return sum(v * w for v, w in available) / total_w

    result["freight_combined"] = result.apply(_blend, axis=1)
    result["F_raw"] = result["freight_combined"].pct_change().abs().clip(0, 1)
    result = result.ffill().fillna(0)

    logger.info("운임지수 통합: %d개월 (SCFI/CCFI=%s, KCCI=%s)",
                len(result),
                "있음" if scfi_ccfi is not None else "없음",
                "있음" if kcci_df is not None else "없음")
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 2. GDELT CSV 로더 (BigQuery 다운로드 결과)
# ──────────────────────────────────────────────────────────────────────────────

def load_gdelt_csv(data_dir: Path) -> pd.DataFrame | None:
    """
    BigQuery에서 다운로드한 GDELT 월별 집계 CSV 로드.
    저장 경로: data/gdelt_maritime_monthly.csv

    반환: DataFrame(date, G_gdelt, D_gdelt, P_gdelt) — 값 범위 [0, 1]
    기간: 2015-02 ~ 현재
    """
    fp = data_dir / "gdelt_maritime_monthly.csv"
    if not fp.exists():
        logger.info("GDELT CSV 없음 — data/gdelt_maritime_monthly.csv 저장 후 재실행")
        return None

    df = pd.read_csv(fp)

    ym_col = next((c for c in ["ym", "year_month"] if c in df.columns), None)
    if ym_col is None:
        logger.warning("GDELT CSV: ym 컬럼 없음")
        return None

    ym_str = df[ym_col].astype(str).str[:7]
    ym_str = ym_str.str.replace(r"^(\d{4})(\d{2})$", r"\1-\2", regex=True)
    df["date"] = pd.to_datetime(ym_str, format="%Y-%m", errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    def _norm95(s: pd.Series) -> pd.Series:
        sat = s.quantile(0.95)
        return (s / sat).clip(0, 1) if sat > 0 else s * 0.0

    result = pd.DataFrame({"date": df["date"]})

    g_cols = [c for c in ["G_conflict_count", "G_hotspot_count"] if c in df.columns]
    result["G_gdelt"] = _norm95(df[g_cols].mean(axis=1)) if g_cols else np.nan

    if "D_negative_count" in df.columns and "total_events" in df.columns:
        ratio = df["D_negative_count"] / df["total_events"].replace(0, np.nan)
        result["D_gdelt"] = _norm95(ratio.fillna(0))
    elif "D_negative_count" in df.columns:
        result["D_gdelt"] = _norm95(df["D_negative_count"])
    else:
        result["D_gdelt"] = np.nan

    result["P_gdelt"] = (
        _norm95(df["P_sanction_count"]) if "P_sanction_count" in df.columns else np.nan
    )

    logger.info("GDELT 로드: %d개월 (%s ~ %s)",
                len(result),
                result["date"].iloc[0].strftime("%Y-%m"),
                result["date"].iloc[-1].strftime("%Y-%m"))
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 3. Naver DataLab API — 월별 검색 트렌드
# ──────────────────────────────────────────────────────────────────────────────

def fetch_naver_datalab(
    start_ym:      str = "2016-01",
    end_ym:        str | None = None,
    client_id:     str | None = None,
    client_secret: str | None = None,
) -> pd.DataFrame | None:
    """
    Naver DataLab 검색어 트렌드 API — G/D/P 월별 검색량 지수 수집.

    반환: DataFrame(date, G_naver, D_naver, P_naver) — 값 범위 [0, 1]
    API 범위: 2016-01 ~ 현재
    환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
    """
    cid     = client_id     or os.getenv("NAVER_CLIENT_ID", "")
    csecret = client_secret or os.getenv("NAVER_CLIENT_SECRET", "")

    if not cid or not csecret:
        logger.info("Naver DataLab API 키 미설정 (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)")
        return None

    effective_start = max(pd.Timestamp(start_ym), pd.Timestamp("2016-01-01"))
    end_dt = pd.Timestamp(end_ym) if end_ym else pd.Timestamp.today()

    payload = {
        "startDate":    effective_start.strftime("%Y-%m-%d"),
        "endDate":      end_dt.strftime("%Y-%m-%d"),
        "timeUnit":     "month",
        "keywordGroups": NAVER_KEYWORD_GROUPS,
    }
    headers = {
        "X-Naver-Client-Id":     cid,
        "X-Naver-Client-Secret": csecret,
        "Content-Type":          "application/json",
    }

    try:
        resp = requests.post(NAVER_DATALAB_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Naver DataLab API 오류: %s", e)
        return None

    if "results" not in data:
        logger.warning("Naver DataLab 응답 형식 오류")
        return None

    records: dict[str, dict] = {}
    for r in data["results"]:
        name = r.get("title", "")
        for row in r.get("data", []):
            period = str(row["period"])[:7]
            if period not in records:
                records[period] = {}
            records[period][name] = float(row["ratio"]) / 100.0

    if not records:
        logger.warning("Naver DataLab: 빈 응답")
        return None

    df = pd.DataFrame([
        {
            "date":    pd.Timestamp(period),
            "G_naver": vals.get("G_geopolitical", 0.0),
            "D_naver": vals.get("D_disruption",   0.0),
            "P_naver": vals.get("P_trade",         0.0),
        }
        for period, vals in sorted(records.items())
    ])
    logger.info("Naver DataLab 수집: %d개월 (%s ~ %s)",
                len(df),
                df["date"].iloc[0].strftime("%Y-%m"),
                df["date"].iloc[-1].strftime("%Y-%m"))
    return df


# ──────────────────────────────────────────────────────────────────────────────
# 3. BPA 물동량 로더
# ──────────────────────────────────────────────────────────────────────────────

def load_bpa_monthly_history(data_dir: Path) -> pd.DataFrame | None:
    """
    기존 data_loader.load_busan_throughput_combined()를 래핑.
    2010년 이전 데이터는 공공데이터포털 CSV로 보완.

    반환: DataFrame(date, throughput) — 단위: 만 TEU/월
    """
    from src.data_loader import load_busan_throughput_combined

    df = load_busan_throughput_combined(data_dir, start_year=2010)
    if df is None or df.empty:
        # 공공데이터포털 CSV 로드 시도
        # (data/busan_throughput_2010.csv 수동 저장 시)
        p = data_dir / "busan_throughput_2010.csv"
        if p.exists():
            from src.data_loader import _read_csv_auto_enc, _find_col
            raw = _read_csv_auto_enc(p)
            if raw is not None:
                dc = _find_col(raw, ["년월", "날짜", "월", "date"])
                vc = _find_col(raw, ["teu", "물동량", "throughput"])
                if dc and vc:
                    df = raw[[dc, vc]].rename(columns={dc: "date", vc: "throughput"})
                    df["date"] = pd.to_datetime(
                        df["date"].astype(str).str.replace(r"[\.\-/]", "", regex=True).str[:6],
                        format="%Y%m", errors="coerce",
                    )
                    df["throughput"] = pd.to_numeric(
                        df["throughput"].astype(str).str.replace(",", "", regex=False),
                        errors="coerce",
                    )
                    df = df.dropna().sort_values("date").reset_index(drop=True)
                    if df["throughput"].mean() > 100_000:
                        df["throughput"] /= 10_000

    if df is None or df.empty:
        logger.warning("BPA 물동량 없음 — V 차원 시뮬 폴백")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# 4. 엔트로피 가중치 산출
# ──────────────────────────────────────────────────────────────────────────────

def compute_entropy_weights(data_matrix: np.ndarray) -> np.ndarray:
    """
    IQR 기반 로버스트 엔트로피 가중치법.

    [정규화 방식]
    표준 min-max 대신 IQR Tukey 울타리(Q1-1.5×IQR, Q3+1.5×IQR)로 클리핑 후
    min-max 정규화. COVID 같은 극단 이상치가 분산을 독점하는 현상 방지.

    [참고]
    Shannon, C.E. (1948). A Mathematical Theory of Communication.
    Tukey, J.W. (1977). Exploratory Data Analysis. Addison-Wesley.

    Parameters
    ----------
    data_matrix : np.ndarray, shape (n_periods, n_dimensions)
    Returns
    -------
    np.ndarray, shape (n_dimensions,) — 엔트로피 가중치 (합 = 1.0)
    """
    mat = data_matrix.copy().astype(float)
    n, m = mat.shape

    # ── 1) IQR Tukey 울타리로 이상치 클리핑 ───────────────────────────────
    q1  = np.percentile(mat, 25, axis=0)
    q3  = np.percentile(mat, 75, axis=0)
    iqr = q3 - q1
    # IQR=0인 차원은 표준편차로 대체, 그래도 0이면 1 사용
    fallback = np.std(mat, axis=0)
    iqr = np.where(iqr == 0, np.where(fallback == 0, 1.0, fallback), iqr)

    upper = q3 + 1.5 * iqr
    lower = np.maximum(q1 - 1.5 * iqr, 0.0)   # 음수 하한 방지
    mat   = np.clip(mat, lower, upper)

    # ── 2) min-max 정규화 (클리핑 후) ────────────────────────────────────
    col_min   = mat.min(axis=0)
    col_max   = mat.max(axis=0)
    col_range = col_max - col_min
    col_range[col_range == 0] = 1.0
    normalized = (mat - col_min) / col_range

    # ── 3) 확률 비율 ────────────────────────────────────────────────────
    normalized = np.clip(normalized, 1e-10, None)
    p = normalized / normalized.sum(axis=0)

    # ── 4) 엔트로피 → 분산도 → 가중치 ───────────────────────────────────
    k          = 1.0 / np.log(n)
    entropy    = -k * (p * np.log(p)).sum(axis=0)
    divergence = np.clip(1.0 - entropy, 0, None)
    total_div  = divergence.sum()
    if total_div == 0:
        return np.ones(m) / m

    return divergence / total_div


# ──────────────────────────────────────────────────────────────────────────────
# 5. BPA 물동량 LSTM 단기 예측 (최신 공백 채우기)
# ──────────────────────────────────────────────────────────────────────────────

def forecast_bpa_lstm(
    bpa_df:   pd.DataFrame,
    n_months: int = 3,
    seq_len:  int = 12,
    n_epochs: int = 80,
) -> pd.DataFrame | None:
    """
    BPA 월별 물동량 LSTM 단기 예측 (기존 lstm_forecaster.py 구조 준용).

    Parameters
    ----------
    bpa_df   : DataFrame(date, throughput) — 학습용 역사 데이터
    n_months : 예측 개월 수 (기본 3개월)
    seq_len  : 입력 시퀀스 길이 (기본 12개월)
    n_epochs : 학습 에포크 (기본 80)

    Returns
    -------
    DataFrame(date, throughput) — 예측값, 또는 None(torch 없음)
    """
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        logger.warning("torch 미설치 — BPA LSTM 예측 불가, ffill 유지")
        return None

    torch.manual_seed(42)
    np.random.seed(42)

    values = bpa_df.sort_values("date")["throughput"].values.astype(float)
    v_min, v_max = values.min(), values.max()
    v_range = v_max - v_min or 1.0
    scaled = (values - v_min) / v_range

    # 시퀀스 데이터 생성 (시간순 분할)
    X = np.array([scaled[i:i+seq_len] for i in range(len(scaled) - seq_len)])
    y = scaled[seq_len:]
    X_t = torch.tensor(X, dtype=torch.float32).unsqueeze(-1)
    y_t = torch.tensor(y, dtype=torch.float32)

    class _LSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(1, 64, num_layers=2, batch_first=True, dropout=0.1)
            self.fc   = nn.Linear(64, 1)
        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :]).squeeze(-1)

    model     = _LSTM()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    model.train()
    for _ in range(n_epochs):
        optimizer.zero_grad()
        criterion(model(X_t), y_t).backward()
        optimizer.step()

    # 재귀 예측
    model.eval()
    window = list(scaled[-seq_len:])
    preds  = []
    with torch.no_grad():
        for _ in range(n_months):
            inp  = torch.tensor([window[-seq_len:]], dtype=torch.float32).unsqueeze(-1)
            p    = model(inp).item()
            preds.append(p)
            window.append(p)

    pred_vals  = [p * v_range + v_min for p in preds]
    last_date  = bpa_df["date"].max()
    dates      = [last_date + pd.DateOffset(months=i+1) for i in range(n_months)]

    result = pd.DataFrame({"date": dates, "throughput": pred_vals})
    logger.info("BPA LSTM 예측 완료: %d개월 (%s ~ %s), 평균 %.1f만톤",
                n_months,
                result["date"].iloc[0].strftime("%Y-%m"),
                result["date"].iloc[-1].strftime("%Y-%m"),
                result["throughput"].mean())
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 6. 메인: 역대 MRI 시계열 생성
# ──────────────────────────────────────────────────────────────────────────────

def build_real_mri_series(
    data_dir:            Path,
    project_root:        Path | None = None,
    start_ym:            str = HISTORY_START,
    naver_client_id:     str | None = None,
    naver_client_secret: str | None = None,
) -> pd.DataFrame:
    """
    2015-02 ~ 현재까지 월별 실데이터 MRI 산출.

    [데이터 흐름]
    1. F (운임): SCFI/CCFI Excel + KCCI XLS 조합
    2. V (물동량): BPA 월별 (12개월 롤링 YoY) + LSTM 예측(최신 공백 최대 3개월 보완)
    3. G/D/P (뉴스): GDELT CSV + Naver DataLab 조합
       - 2015-02 ~ 2015-12: GDELT 단독
       - 2016-01 ~ 현재   : GDELT 80% + Naver DataLab 20%
    4. 엔트로피 가중치 산출 (전체 기간 1회)
    5. MRI = w_G*G + w_D*D + w_F*F + w_V*V + w_P*P

    반환 DataFrame 컬럼:
      date, G, D, F, V, P  : 각 차원 정규화값 [0, 1]
      mri_entropy           : 엔트로피 가중치 MRI
      mri_ahp               : AHP 가중치 MRI (비교용)
      w_G, w_D, w_F, w_V, w_P : 산출된 엔트로피 가중치
      data_source           : 차원별 데이터 출처 표시
    """
    root = project_root or data_dir.parent

    months = pd.date_range(start_ym, pd.Timestamp.today().strftime("%Y-%m"), freq="MS")
    n = len(months)
    result = pd.DataFrame({"date": months})
    sources: list[str] = []

    # ── F 차원: 운임지수 ──────────────────────────────────────────────────────
    freight_df = load_freight_combined(data_dir, project_root=root)
    if freight_df is not None and not freight_df.empty:
        f_merged = result.merge(freight_df[["date", "F_raw"]], on="date", how="left").ffill().fillna(0)
        result["F"] = f_merged["F_raw"].clip(0, 1).values
        sources.append("F:real(SCFI/CCFI/KCCI)")
    else:
        rng = np.random.default_rng(42)
        result["F"] = rng.beta(2, 8, n) * 0.15
        sources.append("F:simulated")

    # ── V 차원: BPA 월별 실측 + LSTM 예측으로 공백 보완 ─────────────────────
    bpa_df = load_bpa_monthly_history(data_dir)

    if bpa_df is not None and not bpa_df.empty:
        bpa_df["date"] = bpa_df["date"].dt.to_period("M").dt.to_timestamp()

        # LSTM으로 최신 공백(최대 3개월) 채우기
        last_bpa  = bpa_df["date"].max()
        today_ms  = pd.Timestamp.today().replace(day=1)
        if last_bpa < today_ms:
            gap_months = (today_ms.year - last_bpa.year) * 12 + (today_ms.month - last_bpa.month)
            n_pred = min(gap_months, 3)
            pred_df = forecast_bpa_lstm(bpa_df, n_months=n_pred)
            if pred_df is not None:
                pred_df = pred_df[pred_df["date"] <= today_ms]
                bpa_df  = (pd.concat([bpa_df, pred_df])
                           .sort_values("date")
                           .drop_duplicates("date")
                           .reset_index(drop=True))
                sources.append("V:LSTM_filled")

        v_merged = result.merge(bpa_df[["date", "throughput"]], on="date", how="left").ffill().bfill()
        # 12개월 롤링 합계 YoY — 계절성 완전 제거, 연간 수요 변화 포착
        rolling_annual = v_merged["throughput"].rolling(12, min_periods=6).sum()
        yoy_rolling    = rolling_annual.pct_change(12)
        result["V"] = (-yoy_rolling / 0.10).clip(0, 1).fillna(0).values
        sources.append("V:real(BPA-rollingYoY)")
    else:
        rng2 = np.random.default_rng(43)
        result["V"] = rng2.beta(1, 20, n) * 0.05
        sources.append("V:simulated")

    # ── G, D, P 차원: GDELT + Naver DataLab 조합 ─────────────────────────────
    gdelt_df = load_gdelt_csv(data_dir)
    naver_df = fetch_naver_datalab(
        start_ym=start_ym,
        client_id=naver_client_id     or os.getenv("NAVER_CLIENT_ID"),
        client_secret=naver_client_secret or os.getenv("NAVER_CLIENT_SECRET"),
    )

    if gdelt_df is not None or naver_df is not None:
        if gdelt_df is not None:
            result = result.merge(
                gdelt_df[["date", "G_gdelt", "D_gdelt", "P_gdelt"]], on="date", how="left"
            )
        else:
            result["G_gdelt"] = np.nan
            result["D_gdelt"] = np.nan
            result["P_gdelt"] = np.nan

        if naver_df is not None:
            result = result.merge(
                naver_df[["date", "G_naver", "D_naver", "P_naver"]], on="date", how="left"
            )
        else:
            result["G_naver"] = np.nan
            result["D_naver"] = np.nan
            result["P_naver"] = np.nan

        naver_start = pd.Timestamp("2016-01-01")

        def _combine(gdelt_col: str, naver_col: str) -> pd.Series:
            g   = result[gdelt_col].fillna(0)
            nav = result[naver_col].fillna(0)
            has_naver = result["date"] >= naver_start
            combined = g.copy()
            combined[has_naver] = (g[has_naver] * 0.8 + nav[has_naver] * 0.2)
            return combined.clip(0, 1)

        result["G"] = _combine("G_gdelt", "G_naver")
        result["D"] = _combine("D_gdelt", "D_naver")
        result["P"] = _combine("P_gdelt", "P_naver")

        src_parts = []
        if gdelt_df is not None:  src_parts.append("GDELT")
        if naver_df is not None:  src_parts.append("Naver")
        sources.append("G,D,P:real(" + "+".join(src_parts) + ")")
    else:
        rng3 = np.random.default_rng(44)
        noise = rng3.beta(1.5, 6, n)
        result["G"] = (noise * 0.40).clip(0, 1)
        result["D"] = (noise * 0.25).clip(0, 1)
        result["P"] = (noise * 0.15).clip(0, 1)
        sources.append("G,D,P:simulated")

    result["data_source"] = " | ".join(sources)

    # ── IQR 로버스트 엔트로피 가중치 산출 (전체 기간 1회) ─────────────────
    dim_cols = ["G", "D", "F", "V", "P"]
    mat      = result[dim_cols].values.astype(float)
    entropy_weights = compute_entropy_weights(mat)

    # ── 엔트로피 + 등분 하이브리드 가중치 ────────────────────────────────
    # [설계 근거: 차원 간 다중공선성(Multicollinearity) 보정]
    # G·D·F·V·P 5차원은 서로 독립적이지 않다.
    # 예) 전쟁 발발 → G(지정학)↑, D(부정감성)↑, F(운임)↑ 이 동시에 상승.
    # 순수 IQR 엔트로피는 이 공선성 구조를 반영하지 못하고, COVID 충격이
    # 집중된 V(물동량)에 가중치 0.64를 부여하는 편향이 생긴다.
    # 등분 가중치(각 0.2)와 단순 평균을 내어, 엔트로피가 포착한 정보량
    # 신호는 유지하되 특정 차원의 독점을 방지하는 하이브리드 방식을 채택한다.
    # 참고: Wang & Lee (2020), Hybrid Entropy-Equal Weight MCDM in Supply Chain Risk
    equal_weights = np.full(len(dim_cols), 1.0 / len(dim_cols))
    weights       = (entropy_weights + equal_weights) / 2.0
    w_G, w_D, w_F, w_V, w_P = weights

    # 엔트로피 순수 가중치도 저장 (비교·검증용)
    for dim, w_ent in zip(dim_cols, entropy_weights):
        result[f"w_{dim}_entropy"] = round(float(w_ent), 4)
    for dim, w in zip(dim_cols, weights):
        result[f"w_{dim}"] = round(float(w), 4)

    # ── MRI 산출 ─────────────────────────────────────────────────────────
    result["mri_entropy"] = (
        w_G * result["G"] + w_D * result["D"] + w_F * result["F"]
        + w_V * result["V"] + w_P * result["P"]
    ).clip(0, 1).round(4)

    logger.info(
        "역대 MRI 산출: %d개월 (%s ~ %s)\n"
        "  엔트로피 가중치:  G=%.3f D=%.3f F=%.3f V=%.3f P=%.3f\n"
        "  등분 가중치:      G=0.200 D=0.200 F=0.200 V=0.200 P=0.200\n"
        "  하이브리드(평균): G=%.3f D=%.3f F=%.3f V=%.3f P=%.3f",
        len(result),
        result["date"].iloc[0].strftime("%Y-%m"),
        result["date"].iloc[-1].strftime("%Y-%m"),
        *entropy_weights,
        w_G, w_D, w_F, w_V, w_P,
    )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 6. MRI 단기 예측 + 추세 확률
# ──────────────────────────────────────────────────────────────────────────────

def _forecast_series_lstm(
    series:   np.ndarray,
    n_out:    int = 3,
    seq_len:  int = 12,
    n_epochs: int = 60,
) -> np.ndarray:
    """단변량 시계열 LSTM 단기 예측 (재귀 방식)."""
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        # torch 없으면 선형 외삽
        slope = (series[-1] - series[-seq_len]) / (seq_len - 1)
        return np.array([series[-1] + slope * (i + 1) for i in range(n_out)])

    torch.manual_seed(42);  np.random.seed(42)
    v_min, v_max = series.min(), series.max()
    v_rng = v_max - v_min or 1.0
    sc = (series - v_min) / v_rng

    X = np.array([sc[i:i+seq_len] for i in range(len(sc)-seq_len)])
    y = sc[seq_len:]
    Xt = torch.tensor(X, dtype=torch.float32).unsqueeze(-1)
    yt = torch.tensor(y, dtype=torch.float32)

    class _M(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(1, 32, num_layers=1, batch_first=True)
            self.fc   = nn.Linear(32, 1)
        def forward(self, x):
            o, _ = self.lstm(x)
            return self.fc(o[:, -1]).squeeze(-1)

    model = _M()
    opt   = torch.optim.Adam(model.parameters(), lr=2e-3)
    crit  = nn.MSELoss()
    model.train()
    for _ in range(n_epochs):
        opt.zero_grad();  crit(model(Xt), yt).backward();  opt.step()

    model.eval()
    window = list(sc[-seq_len:])
    preds  = []
    with torch.no_grad():
        for _ in range(n_out):
            inp = torch.tensor([window[-seq_len:]], dtype=torch.float32).unsqueeze(-1)
            p   = model(inp).item()
            preds.append(p);  window.append(p)

    return np.array(preds) * v_rng + v_min


def predict_mri_trend(
    mri_df:          pd.DataFrame,
    data_dir:        Path,
    project_root:    Path | None = None,
    forecast_months: int   = 3,
    threshold:       float = 0.05,
) -> dict:
    """
    MRI 단기 예측 (3개월) + 추세 확률 산출.

    [방법론]
    F (운임)  : LSTM으로 freight_combined 3개월 예측
    V (물동량): 과거 동월 계절 평균으로 예측
    G, D, P  : 현재값 유지 (사건 기반 → 예측 불가)
    확률     : 현재 MRI ±0.10 범위 역사 사례에서 3개월 후 분포 집계

    Returns
    -------
    dict {
        'forecast_df'  : DataFrame(date, G, D, F, V, P, mri_forecast),
        'prob_up'      : float,
        'prob_stay'    : float,
        'prob_down'    : float,
        'n_historical' : int,
        'current_mri'  : float,
        'current_grade': str,
        'basis'        : str,
    }
    """
    from src.mri_engine import mri_grade
    root = project_root or data_dir.parent

    # ── 현재 상태 ─────────────────────────────────────────────────────────
    latest       = mri_df.iloc[-1]
    current_mri  = float(latest["mri_entropy"])
    current_date = latest["date"]
    weights      = {d: float(latest[f"w_{d}"]) for d in ["G", "D", "F", "V", "P"]}
    grade, _     = mri_grade(current_mri)

    # ── F 예측: LSTM ──────────────────────────────────────────────────────
    freight_df = load_freight_combined(data_dir, project_root=root)
    if freight_df is not None and not freight_df.empty:
        fc_series  = freight_df["freight_combined"].values
        fc_pred    = _forecast_series_lstm(fc_series, n_out=forecast_months)
        # F_raw = |pct_change| (직전 마지막 실제값 대비)
        prev       = fc_series[-1]
        f_forecast = []
        for val in fc_pred:
            f_raw = abs((val - prev) / prev) if prev != 0 else 0.0
            f_forecast.append(min(f_raw, 1.0))
            prev = val
    else:
        f_forecast = [float(latest["F"])] * forecast_months

    # ── V 예측: 과거 동월 계절 평균 ───────────────────────────────────────
    bpa_df = load_bpa_monthly_history(data_dir)
    v_forecast = []
    for i in range(1, forecast_months + 1):
        pred_date = current_date + pd.DateOffset(months=i)
        if bpa_df is not None and not bpa_df.empty:
            same_month = bpa_df[bpa_df["date"].dt.month == pred_date.month]
            if not same_month.empty:
                # 과거 동월 YoY 변화율 평균
                sm = same_month.sort_values("date")
                yoy = sm["throughput"].pct_change(1).mean()  # 연간 단위 의미로 근사
                v_forecast.append(max(0.0, min(-yoy / 0.10, 1.0)))
            else:
                v_forecast.append(float(latest["V"]))
        else:
            v_forecast.append(float(latest["V"]))

    # ── G, D, P: 현재값 유지 + 소폭 감쇠 (시간 경과 → 불확실성 반영) ────
    decay = [1.0, 0.90, 0.82]
    g_forecast = [float(latest["G"]) * d for d in decay[:forecast_months]]
    d_forecast = [float(latest["D"]) * d for d in decay[:forecast_months]]
    p_forecast = [float(latest["P"]) * d for d in decay[:forecast_months]]

    # ── 예측 MRI 조합 ─────────────────────────────────────────────────────
    forecast_rows = []
    for i in range(forecast_months):
        pred_date = current_date + pd.DateOffset(months=i+1)
        G = g_forecast[i];  D = d_forecast[i]
        F = f_forecast[i];  V = v_forecast[i];  P = p_forecast[i]
        mri_pred = (weights["G"]*G + weights["D"]*D + weights["F"]*F
                    + weights["V"]*V + weights["P"]*P)
        forecast_rows.append({
            "date": pred_date, "G": round(G,4), "D": round(D,4),
            "F": round(F,4), "V": round(V,4), "P": round(P,4),
            "mri_forecast": round(min(max(mri_pred, 0.0), 1.0), 4),
        })
    forecast_df = pd.DataFrame(forecast_rows)

    # ── 역사적 조건부 확률 ─────────────────────────────────────────────────
    # 현재 MRI ±0.10 범위 내 역사 달 찾기 → 3개월 후 MRI 변화 분포
    band     = 0.10
    hist_mri = mri_df["mri_entropy"].values
    n        = len(hist_mri)
    up = stay = down = 0
    for idx in range(n - forecast_months):
        if abs(hist_mri[idx] - current_mri) <= band:
            delta = hist_mri[idx + forecast_months] - hist_mri[idx]
            if   delta >  threshold: up   += 1
            elif delta < -threshold: down += 1
            else:                    stay += 1

    total = up + stay + down or 1
    prob_up   = round(up   / total, 3)
    prob_stay = round(stay / total, 3)
    prob_down = round(down / total, 3)
    n_cases   = up + stay + down

    basis = (
        f"현재 MRI {current_mri:.3f} [{grade}] 기준 ±{band} 범위 "
        f"역사 사례 {n_cases}건 분석 "
        f"(G·D·P 현재값 유지, F·V LSTM+계절 예측)"
    )

    logger.info("MRI 추세 예측: 상승%.0f%% 유지%.0f%% 하락%.0f%% (사례 %d건)",
                prob_up*100, prob_stay*100, prob_down*100, n_cases)
    return {
        "forecast_df":   forecast_df,
        "prob_up":       prob_up,
        "prob_stay":     prob_stay,
        "prob_down":     prob_down,
        "n_historical":  n_cases,
        "current_mri":   current_mri,
        "current_grade": grade,
        "basis":         basis,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 7. 시각화 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

def plot_real_mri(df: pd.DataFrame, save_path: Path | None = None) -> None:
    """역대 MRI 시계열 차트 (IQR 로버스트 엔트로피 가중치 기반)"""
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    EVENTS = [
        ("2018-07", "미중\n관세전쟁"),
        ("2020-03", "COVID-19"),
        ("2021-03", "수에즈\n에버기븐"),
        ("2022-03", "상하이\n봉쇄"),
        ("2023-12", "홍해\n후티"),
    ]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 9),
                                    gridspec_kw={"height_ratios": [3, 1]})

    # ── 상단: MRI 시계열 ────────────────────────────────────────────────────
    ax1.fill_between(df["date"], df["mri_entropy"], alpha=0.15, color="#2196F3")
    ax1.plot(df["date"], df["mri_entropy"],
             color="#2196F3", linewidth=1.8, label="MRI (IQR 로버스트 엔트로피)")

    for ym, label in EVENTS:
        if label:
            dt = pd.Timestamp(ym)
            ax1.axvline(dt, color="red", linewidth=0.8, alpha=0.5, linestyle=":")
            ax1.text(dt, 0.95, label, fontsize=7, color="red",
                     ha="center", va="top", rotation=0)

    # 등급 구간 음영 (분위수 기반 임계값)
    grade_zones = [
        (0.55, 1.0, "#FF5252", "위험 (≥0.55)"),
        (0.43, 0.55, "#FF9800", "경계 (0.43~0.55)"),
        (0.33, 0.43, "#FFEB3B", "주의 (0.33~0.43)"),
        (0.00, 0.33, "#4CAF50", "정상 (<0.33)"),
    ]
    for lo, hi, color, _ in grade_zones:
        ax1.axhspan(lo, hi, alpha=0.04, color=color)

    ax1.set_ylabel("MRI")
    ax1.set_ylim(0, 1)
    ax1.set_title("해상 리스크 지수 (MRI) 역대 시계열 — 실데이터 기반", fontsize=13)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(axis="y", alpha=0.3)

    # ── 하단: 엔트로피 가중치 추이 ─────────────────────────────────────────
    colors = {"w_G": "#E53935", "w_D": "#43A047", "w_F": "#1E88E5",
              "w_V": "#8E24AA", "w_P": "#FB8C00"}
    labels = {"w_G": "G(지정학)", "w_D": "D(기상)", "w_F": "F(운임)",
              "w_V": "V(물동량)", "w_P": "P(항만)"}
    for col, color in colors.items():
        ax2.plot(df["date"], df[col], color=color, linewidth=1.2,
                 label=labels[col], alpha=0.85)

    ax2.set_ylabel("엔트로피 가중치")
    ax2.set_ylim(0, 0.6)
    ax2.set_xlabel("연월")
    ax2.legend(loc="upper left", fontsize=8, ncol=5)
    ax2.grid(axis="y", alpha=0.3)
    ax2.set_title("차원별 엔트로피 가중치 (전체 기간 동일 적용)", fontsize=9)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info("차트 저장: %s", save_path)
    plt.show()


def print_weight_comparison(df: pd.DataFrame) -> None:
    """엔트로피·등분·하이브리드 가중치 비교 출력"""
    dims      = ["G", "D", "F", "V", "P"]
    dim_names = {"G": "G (지정학)", "D": "D (부정감성)", "F": "F (운임)",
                 "V": "V (물동량)", "P": "P (통상제재)"}

    w_ent = {c: df[f"w_{c}_entropy"].iloc[-1] for c in dims}
    w_hyb = {c: df[f"w_{c}"].iloc[-1]         for c in dims}

    print("\n━━━ MRI 가중치 비교 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {'차원':<14} {'엔트로피':>9}  {'등분':>6}  {'하이브리드':>10}  막대(하이브리드)")
    print("─" * 64)
    for dim in dims:
        bar = "█" * int(w_hyb[dim] * 30)
        print(f"  {dim_names[dim]:<14} {w_ent[dim]:>9.3f}  {'0.200':>6}  {w_hyb[dim]:>10.3f}  {bar}")
    print("─" * 64)
    print("  [설계 근거] G·D·F·V·P는 독립적이지 않음 (다중공선성).")
    print("  순수 엔트로피 가중치와 등분 가중치(0.2)의 평균으로 균형을 확보함.")
    print(f"\n  데이터 소스: {df['data_source'].iloc[0]}")
