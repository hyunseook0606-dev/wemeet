"""
mri_engine.py — AHP 기반 Maritime Risk Index (MRI) 산출 엔진 (5차원 개선)

[방법론]
Saaty (1980) AHP 쌍대비교 + 실데이터 근거 기반 5차원 재설계.

[5대 리스크 차원 & AHP 가중치]
G (지정학·항로): 0.431 — 봉쇄·전쟁·항로 교란. 운임 최대 100% 영향.
                           근거: UNCTAD 2024 — 홍해 사태 수에즈 통항 42%~90% 감소
D (지연·운항):   0.182 — 출항 지연 일수 정규화 (14일 = 1.0).
                           근거: B1_RED_SEA +14일(케이프타운), B2_HORMUZ +10일
F (운임 변동):   0.253 — 운임 변동률 정규화 (100% 상승 = 1.0).
                           근거: 홍해 사태 피크 운임 100%~200% 상승 (UNCTAD 2024)
V (통행량):      0.090 — 주요 해협 통행량 감소율 정규화 (50% 감소 = 1.0).
                           근거: UNCTAD 2024 수에즈 통항 90% 감소; EIA 호르무즈 20%
P (항만·통상):   0.044 — 파업·관세·혼잡 등 운영 차질.
                           근거: Destatis 2023 독일 항만 파업; USTR 2025 관세 조치

MRI = 0.431·G + 0.182·D + 0.253·F + 0.090·V + 0.044·P   ∈ [0, 1]

[정규화 기준]
  D: delay_days / 14   (14일 = B1_RED_SEA 케이프타운 우회, 최장 사례)
  F: rate_change / 1.0 (100% 상승 = 포화점, 실제 피크 100~200% → 보수적 기준)
  V: vol_drop   / 0.5  (50% 감소 = 포화점, 수에즈 42%~90% → 중간값 기준)

[일관성 검증]
λ_max=5.140, CI=0.035, RI=1.12, CR=3.1% < 10% → 통과
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import MRI_AHP_WEIGHTS, MRI_AHP_MATRIX, MRI_GRADES


# ── AHP 계산 유틸리티 ─────────────────────────────────────────────────────────

def compute_ahp_weights(matrix: list[list[float]]) -> dict:
    """
    AHP 쌍대비교 행렬 → 가중치 벡터 + 일관성 지표 반환.
    열 정규화 후 행 평균 (고유벡터 근사법).
    반환: {weights, lambda_max, CI, CR}
    """
    A = np.array(matrix, dtype=float)
    n = A.shape[0]

    # 열 정규화
    col_sums = A.sum(axis=0)
    A_norm   = A / col_sums

    # 가중치 = 행 평균
    w = A_norm.mean(axis=1)

    # λ_max 계산
    Aw       = A @ w
    lambdas  = Aw / w
    lam_max  = lambdas.mean()

    # 일관성 지표
    RI_table = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32}
    CI = (lam_max - n) / (n - 1)
    RI = RI_table.get(n, 1.32)
    CR = CI / RI if RI > 0 else 0

    return {'weights': w.tolist(), 'lambda_max': lam_max, 'CI': CI, 'CR': CR}


# ── 오늘 MRI 계산 ─────────────────────────────────────────────────────────────

def calc_today_mri(news_df: pd.DataFrame,
                   freight_df: pd.DataFrame | None = None) -> float:
    """
    오늘 MRI = 0.431·G + 0.182·D + 0.253·F + 0.090·V + 0.044·P

    [포화점 설계 원칙]
    뉴스 비율은 RSS 전체 기사 중 해당 카테고리 비중이므로,
    실제 위기 시에도 30% 이상이 단일 카테고리로 분류되기 어렵다.
    → 현실적 포화점을 25~30%로 설정해 시뮬과 스케일 맞춤.

    G: 지정학분쟁 뉴스 비중 / 0.25  (25% = 포화 → 1.0)
    D: 지연 프록시 — G×1.0 + 기상×0.36  (G 재활용, 포화점 이미 조정)
    F: 운임급등 뉴스/0.20 × 50% + KCCI 월변동률/0.15 × 50%
       KCCI 현실 범위: 월 2~15% 변동 → 포화 15%
    V: KCCI 월 감소율/0.10 (10% 감소 = 포화)
       실데이터 없으면 G×0.84 사용 (수에즈 42%/50%=0.84 비례)
    P: (파업+관세) 뉴스 비중 / 0.20  (20% = 포화 → 1.0)
    """
    if news_df.empty or 'pred_category' not in news_df.columns:
        return 0.0

    total  = len(news_df)
    counts = news_df['pred_category'].value_counts()

    # G: 지정학·항로 — 포화점 25% (위기 시 RSS 내 최대 현실 비중)
    G = float(np.clip(counts.get('지정학분쟁', 0) / total / 0.25, 0, 1))

    # D: 지연 프록시 (G 포화점 이미 조정된 값 사용)
    weather_raw = counts.get('기상재해', 0) / total / 0.25
    D = float(np.clip(G * 1.0 + weather_raw * 0.36, 0, 1))

    # F: 운임 변동 — 뉴스 포화점 20%, KCCI 포화점 15% 월변동
    freight_news_norm = float(np.clip(counts.get('운임급등', 0) / total / 0.20, 0, 1))
    if freight_df is not None and len(freight_df) >= 2:
        kcci_chg  = freight_df['value'].pct_change().abs().tail(8).mean()
        kcci_norm = float(np.clip(kcci_chg / 0.15, 0, 1))  # 15% 월변동 = 포화
    else:
        kcci_norm = 0.20  # 데이터 없을 때 중간값 기본
    F = float(np.clip(0.5 * freight_news_norm + 0.5 * kcci_norm, 0, 1))

    # V: 통행량 감소 — KCCI 10% 월감소 = 포화 (월간 변동 현실 범위 반영)
    if freight_df is not None and len(freight_df) >= 4:
        vol_chg = freight_df['value'].pct_change().tail(4).mean()
        V = float(np.clip(-vol_chg / 0.10, 0, 1))
    else:
        V = float(np.clip(G * 0.84, 0, 1))  # 수에즈 42%/50%=0.84 × G 비례

    # P: 항만·통상 — 포화점 20%
    P = float(np.clip(
        (counts.get('항만파업', 0) + counts.get('관세정책', 0)) / total / 0.20,
        0, 1
    ))

    W = MRI_AHP_WEIGHTS
    mri = W['G']*G + W['D']*D + W['F']*F + W['V']*V + W['P']*P
    return float(np.clip(mri, 0.0, 1.0))


# ── 역사적 MRI 시계열 (시뮬) ─────────────────────────────────────────────────

def build_mri_series(dates: pd.DatetimeIndex,
                     freight_df: pd.DataFrame | None = None,
                     seed: int = 42) -> np.ndarray:
    """
    역사적 MRI 시계열 생성 — 5차원 실데이터 근거 기반 시뮬.

    [정규화 기준]
    D: delay_days / 14   (14일 = B1_RED_SEA 케이프타운 우회)
    F: rate_chg   / 1.0  (100% 상승 = 포화, UNCTAD 2024 홍해 피크 기준)
    V: vol_drop   / 0.5  (50% 감소 = 포화, UNCTAD 수에즈 42%~90% 기준)

    [이벤트]
    홍해 사태    2023-12~2024-06: D=1.0(14일), F≈0.5(50%), V≈0.84~1.0
    미중 관세    2025-04~:        D=0.50(7일), F=0.15,      P↑
    이란 위기    2025-06~2026-02: D=0.21(3일), G↑(위기감)
    호르무즈봉쇄 2026-03~:        D=0.71(10일),F≈0.5~0.7,  V≈1.0
    반환: shape (len(dates),) float [0,1]
    """
    rng = np.random.default_rng(seed)
    M   = len(dates)

    # 이벤트 마스크
    hong_hae      = (dates >= '2023-12-01') & (dates <= '2024-06-30')
    tariff        = dates >= '2025-04-01'
    iran_crisis   = (dates >= '2025-06-01') & (dates < '2026-03-01')
    hormuz_actual = dates >= '2026-03-01'
    months        = np.array([d.month for d in dates])
    typhoon_szn   = (months >= 6) & (months <= 9)

    # ── G: 지정학·항로 ─────────────────────────────────────────────────────
    G = rng.beta(1.5, 8, M) * 0.3
    G[hong_hae]      = np.clip(G[hong_hae]      + rng.uniform(0.5, 0.8, hong_hae.sum()),      0, 1)
    G[tariff]        = np.clip(G[tariff]         + 0.25,                                        0, 1)
    G[iran_crisis]   = np.clip(G[iran_crisis]    + rng.uniform(0.15, 0.30, iran_crisis.sum()), 0, 1)
    G[hormuz_actual] = np.clip(G[hormuz_actual]  + rng.uniform(0.50, 0.70, hormuz_actual.sum()), 0, 1)

    # ── D: 지연·운항 (delay_days / 14 정규화) ──────────────────────────────
    # B1_RED_SEA=14일→1.0, B2_HORMUZ=10일→0.71, C2_DROUGHT=7일→0.50
    # B3_TARIFF=7일→0.50, C1_TYPHOON=5일→0.36
    D = rng.beta(1, 20, M) * 0.05                                            # 평소 거의 0
    D[hong_hae]      = np.clip(D[hong_hae]      + 1.00,                                       0, 1)  # 14/14
    D[tariff]        = np.clip(D[tariff]         + 0.50,                                       0, 1)  # 7/14
    D[iran_crisis]   = np.clip(D[iran_crisis]    + 0.21,                                       0, 1)  # 3/14
    D[hormuz_actual] = np.clip(D[hormuz_actual]  + 0.71,                                       0, 1)  # 10/14
    typhoon_idx      = typhoon_szn & ~hong_hae & ~tariff & ~iran_crisis & ~hormuz_actual
    if typhoon_idx.sum() > 0:
        D[typhoon_idx] = np.clip(D[typhoon_idx] + 0.36 * rng.beta(2, 5, typhoon_idx.sum()),   0, 1)  # 5/14

    # ── F: 운임 변동 (rate_change / 1.0 정규화, 100%=포화) ─────────────────
    if freight_df is not None and len(freight_df) >= 6:
        monthly = (
            freight_df.set_index('date')['value']
            .resample('MS').mean()
            .reindex(dates, method='nearest')
        )
        chg   = monthly.pct_change().fillna(0).abs()
        F_arr = np.clip(chg.values / 1.0, 0, 1)          # 100% 변동 = 포화
    else:
        F_arr = rng.beta(2, 7, M) * 0.15
        F_arr[hong_hae]      = np.clip(F_arr[hong_hae]      + rng.uniform(0.30, 0.60, hong_hae.sum()),      0, 1)
        F_arr[tariff]        = np.clip(F_arr[tariff]         + 0.15,                                          0, 1)
        F_arr[iran_crisis]   = np.clip(F_arr[iran_crisis]    + 0.10,                                          0, 1)
        F_arr[hormuz_actual] = np.clip(F_arr[hormuz_actual]  + rng.uniform(0.40, 0.70, hormuz_actual.sum()), 0, 1)

    # ── V: 통행량 감소 (vol_drop / 0.5 정규화, 50%감소=포화) ───────────────
    # UNCTAD 2024: 수에즈 통항 42%~90% 감소 → 42/50=0.84~90/50=1.8(→1.0)
    V_arr = np.zeros(M)
    if hong_hae.sum() > 0:
        V_arr[hong_hae]      = np.clip(rng.uniform(0.42, 0.90, hong_hae.sum())      / 0.5, 0, 1)
    if tariff.sum() > 0:
        V_arr[tariff]        = np.clip(rng.uniform(0.05, 0.20, tariff.sum()),               0, 1)
    if iran_crisis.sum() > 0:
        V_arr[iran_crisis]   = np.clip(rng.uniform(0.03, 0.15, iran_crisis.sum()),          0, 1)
    if hormuz_actual.sum() > 0:
        V_arr[hormuz_actual] = np.clip(rng.uniform(0.60, 1.00, hormuz_actual.sum()),        0, 1)

    # ── P: 항만·통상 ────────────────────────────────────────────────────────
    P_arr = rng.beta(1, 15, M) * 0.3
    P_arr[tariff]        = np.clip(P_arr[tariff]        + 0.30,                                         0, 1)
    P_arr[hormuz_actual] = np.clip(P_arr[hormuz_actual] + 0.25,                                         0, 1)

    # ── AHP 가중합 ──────────────────────────────────────────────────────────
    W   = MRI_AHP_WEIGHTS
    mri = W['G']*G + W['D']*D + W['F']*F_arr + W['V']*V_arr + W['P']*P_arr
    return np.clip(mri, 0.0, 1.0)


def mri_grade(mri: float) -> tuple[str, str]:
    """MRI 점수 → (등급 문자열, hex 색상)."""
    for threshold, label, color in MRI_GRADES:
        if mri >= threshold:
            return label, color
    return MRI_GRADES[-1][1], MRI_GRADES[-1][2]


def mri_sub_indices(news_df: pd.DataFrame,
                    freight_df: pd.DataFrame | None = None) -> dict:
    """
    MRI 5대 하위 지수 반환 (투명성 확보용).
    발표 시 '어떤 요인이 주도하는가' 설명에 활용.
    calc_today_mri()와 동일한 산식 사용.
    """
    if news_df.empty or 'pred_category' not in news_df.columns:
        return {'G': 0.0, 'D': 0.0, 'F': 0.0, 'V': 0.0, 'P': 0.0}

    total  = len(news_df)
    counts = news_df['pred_category'].value_counts()

    G = float(np.clip(counts.get('지정학분쟁', 0) / total / 0.25, 0, 1))

    weather_raw = float(counts.get('기상재해', 0) / total / 0.25)
    D = float(np.clip(G * 1.0 + weather_raw * 0.36, 0, 1))

    freight_news_norm = float(np.clip(counts.get('운임급등', 0) / total / 0.20, 0, 1))
    if freight_df is not None and len(freight_df) >= 2:
        kcci_norm = float(np.clip(
            freight_df['value'].pct_change().abs().tail(8).mean() / 0.15, 0, 1
        ))
    else:
        kcci_norm = 0.20
    F = float(np.clip(0.5 * freight_news_norm + 0.5 * kcci_norm, 0, 1))

    if freight_df is not None and len(freight_df) >= 4:
        vol_chg = freight_df['value'].pct_change().tail(4).mean()
        V = float(np.clip(-vol_chg / 0.10, 0, 1))
    else:
        V = float(np.clip(G * 0.84, 0, 1))

    P = float(np.clip(
        (counts.get('항만파업', 0) + counts.get('관세정책', 0)) / total / 0.20,
        0, 1
    ))

    return {'G': G, 'D': D, 'F': F, 'V': V, 'P': P}
