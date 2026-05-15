"""
data_loader.py — KCCI 운임지수 / 부산항 물동량 / ECOS 거시경제 변수 로더
실데이터 없으면 None 반환 → 호출자에서 시뮬로 폴백
"""
from __future__ import annotations
import os
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ── KCCI ──────────────────────────────────────────────────────────────────────

def load_kcci(data_dir: Path, use_real: bool = True) -> pd.DataFrame | None:
    """
    KCCI 운임지수 로더.
    우선순위: ① XLS 파일 (data/freight_index/*.xls)
              ② kcci_weekly.csv (XLS 합쳐진 결과)
              ③ kcci.csv (구형 CSV)
    반환: DataFrame(date: datetime, value: float) — 주별 KCCI 종합지수
    """
    if not use_real:
        return None

    # 1순위: XLS 파일 또는 합쳐진 주간 CSV (freight_index_loader)
    try:
        from src.freight_index_loader import load_kcci_weekly
        df = load_kcci_weekly(data_dir)
        if df is not None and not df.empty:
            logger.info('KCCI 주간 XLS 로드: %d주', len(df))
            return df
    except ImportError:
        pass

    # 2순위: kcci.csv (구형 포맷 호환)
    p = data_dir / 'kcci.csv'
    if not p.exists():
        logger.info('kcci.csv 없음 — 시뮬 폴백')
        return None

    df = _read_csv_auto_enc(p)
    if df is None:
        return None

    date_col = _find_col(df, ['일자', '발표', '기준', '날짜', 'date'])
    val_col  = _find_col(df, ['kcci', '종합', '지수', 'value', 'index'])
    if not date_col or not val_col:
        logger.warning('KCCI 컬럼 감지 실패')
        return None

    df = df[[date_col, val_col]].rename(columns={date_col: 'date', val_col: 'value'})
    df['date']  = pd.to_datetime(df['date'], errors='coerce')
    df['value'] = pd.to_numeric(
        df['value'].astype(str).str.replace(',', '', regex=False), errors='coerce'
    )
    df = df.dropna().sort_values('date').reset_index(drop=True)
    logger.info('KCCI CSV 로드: %d건', len(df))
    return df


# ── 부산항 물동량 ─────────────────────────────────────────────────────────────

def load_throughput(data_dir: Path, use_real: bool = True) -> pd.DataFrame | None:
    """
    부산항 컨테이너 물동량 CSV 로드.
    단위 자동 변환 → 만 TEU. 반환: DataFrame(date: datetime, throughput: float) or None
    """
    if not use_real:
        return None
    p = data_dir / 'busan_throughput.csv'
    if not p.exists():
        logger.info('busan_throughput.csv 없음 — 시뮬 폴백')
        return None

    df = _read_csv_auto_enc(p)
    if df is None:
        return None

    date_col = _find_col(df, ['년월', '기준', '날짜', '월', 'date'])
    vol_col  = _find_col(df, ['teu', '물동량', '처리', 'throughput', 'volume'])
    if not date_col or not vol_col:
        logger.warning('부산항 컬럼 감지 실패')
        return None

    df = df[[date_col, vol_col]].rename(columns={date_col: 'date', vol_col: 'throughput'})
    # 년월 형식 처리 (202401, 2024.01 등)
    df['date'] = pd.to_datetime(
        df['date'].astype(str).str.replace(r'[\.\-/]', '', regex=True).str[:6],
        format='%Y%m', errors='coerce',
    )
    df['throughput'] = pd.to_numeric(
        df['throughput'].astype(str).str.replace(',', '', regex=False), errors='coerce'
    )
    df = df.dropna().sort_values('date').reset_index(drop=True)

    avg = df['throughput'].mean()
    if avg > 100_000:
        df['throughput'] /= 10_000   # TEU → 만 TEU
    elif avg > 1_000:
        df['throughput'] /= 10       # 천 TEU → 만 TEU

    logger.info('부산항 실데이터: %d개월, 평균 %.1f만 TEU', len(df), df['throughput'].mean())
    return df


# ── 부산항 월별 물동량 (항만별물동량 XLS 폴더) ────────────────────────────────

def load_busan_monthly_xls(base_dir: Path) -> pd.DataFrame | None:
    """
    '부산항 월별 물동량' 폴더 구조에서 월별 실측 물동량 로드.

    폴더 구조:
      부산항 월별 물동량/15년/15년 X월.xls          (2015)
      부산항 월별 물동량/16년~26년/국가물류통합정보센터_항만별물동량_*.xls  (2016~)

    각 파일 구조:
      Row 0, Col 4 : 연도 (e.g. "2020")
      Row 1, Col 4 : 월   (e.g. "03월")
      Row 14, Col 4: 부산항 합계 물동량 (톤 R/T)

    반환: DataFrame(date, throughput)  단위: 만 톤/월
    """
    import re as _re

    folder = base_dir / '부산항 월별 물동량'
    if not folder.exists():
        folder = base_dir.parent / '부산항 월별 물동량'
    if not folder.exists():
        logger.info('부산항 월별 물동량 폴더 없음')
        return None

    records = []
    for year_dir in sorted(folder.iterdir()):
        if not year_dir.is_dir():
            continue
        for fp in sorted(year_dir.glob('*.xls*')):
            try:
                df = pd.read_excel(fp, header=None, dtype=str)
                yr_str  = str(df.iloc[0, 4]).strip()
                mon_str = str(df.iloc[1, 4]).strip()
                cargo_str = str(df.iloc[14, 4]).strip().replace(',', '').replace(' ', '')

                yr_m  = _re.search(r'(\d{4})', yr_str)
                mon_m = _re.search(r'(\d+)', mon_str)
                if not yr_m or not mon_m:
                    continue

                year  = int(yr_m.group(1))
                month = int(mon_m.group(1))
                cargo = float(cargo_str)
                if not (1 <= month <= 12 and 2010 <= year <= 2030 and cargo > 0):
                    continue

                records.append({'year': year, 'month': month, 'cargo_ton': cargo})
            except Exception:
                continue

    if not records:
        logger.warning('부산항 월별 물동량: 파싱된 데이터 없음')
        return None

    df_all = pd.DataFrame(records)
    df_all['date'] = pd.to_datetime(
        df_all['year'].astype(str) + '-' + df_all['month'].astype(str).str.zfill(2),
        format='%Y-%m'
    )
    # 중복 제거 (같은 연월 첫 번째 유지)
    df_all = (df_all.sort_values('date')
              .drop_duplicates(subset=['year', 'month'], keep='first')
              .reset_index(drop=True))

    # 누락 월 선형 보간
    full_idx = pd.date_range(df_all['date'].min(), df_all['date'].max(), freq='MS')
    df_all = (df_all.set_index('date')
              .reindex(full_idx)
              ['cargo_ton']
              .interpolate(method='linear')
              .reset_index()
              .rename(columns={'index': 'date', 'cargo_ton': 'throughput'}))
    df_all['throughput'] = (df_all['throughput'] / 10_000).round(2)  # 톤 → 만 톤

    logger.info('부산항 월별 물동량 로드: %d개월 (%s ~ %s), 평균 %.1f만톤',
                len(df_all),
                df_all['date'].iloc[0].strftime('%Y-%m'),
                df_all['date'].iloc[-1].strftime('%Y-%m'),
                df_all['throughput'].mean())
    return df_all


# ── 부산항 연간 Excel + BPA API 결합 ─────────────────────────────────────────

def load_busan_annual_excel(data_dir: Path) -> dict[int, float] | None:
    """
    '전국항 및 부산항 컨테이너 물동량' Excel에서 연도별 부산항 연간 TEU 추출.
    반환: {2010: teu, 2011: teu, ..., 2025: teu}  (가용 연도만 포함)
    """
    candidates = (sorted(data_dir.glob('*컨테이너 물동량*.xlsx')) +
                  sorted(data_dir.glob('*컨테이너*물동량*.xlsx')))
    if not candidates:
        logger.info('물동량 Excel 없음')
        return None
    fp = candidates[-1]
    try:
        df = pd.read_excel(fp, sheet_name=0, header=None)
        year_col, busan_col = 0, 5
        for r in range(min(6, len(df))):
            row_vals = [str(v) for v in df.iloc[r].tolist()]
            if any('연도' in v for v in row_vals):
                year_col = next(i for i, v in enumerate(row_vals) if '연도' in v)
            if any('부산항' in v for v in row_vals):
                busan_col = next(i for i, v in enumerate(row_vals) if '부산항' in v)

        records: dict[int, float] = {}
        for _, row in df.iterrows():
            try:
                yr  = int(float(str(row.iloc[year_col])))
                teu = float(str(row.iloc[busan_col]).replace(',', ''))
                if 2010 <= yr <= 2030 and teu > 1_000_000:
                    records[yr] = teu
            except (ValueError, TypeError):
                continue

        if records:
            yrs = sorted(records)
            logger.info('Excel 부산항 연간 데이터: %d~%d (%d개년)',
                        yrs[0], yrs[-1], len(records))
        return records if records else None
    except Exception as e:
        logger.warning('Excel 파싱 오류: %s', e)
        return None


def load_busan_throughput_combined(data_dir: Path,
                                   start_year: int = 2015) -> pd.DataFrame | None:
    """
    부산항 월별 물동량 통합 로더.

    [데이터 소스 & 우선순위]
    1순위: '부산항 월별 물동량' 폴더 XLS (월별 실측, 2015-01~2026-03)
    2순위: 연간 Excel 계절 분배 (실측 폴더 없을 때 폴백)
    3순위: BPA API (2020~2024)

    반환: DataFrame(date, throughput) 단위: 만 톤/월
    """
    # 1순위: 월별 실측 XLS 폴더
    df_monthly = load_busan_monthly_xls(data_dir.parent)
    if df_monthly is not None and not df_monthly.empty:
        df_monthly = df_monthly[
            df_monthly['date'].dt.year >= start_year
        ].reset_index(drop=True)
        logger.info('부산항 물동량: 월별 실측 XLS 사용 (%d개월)', len(df_monthly))
        return df_monthly

    # 2순위: 연간 Excel 계절 분배
    from src.real_data_fetcher import fetch_bpa_throughput, _SEASONAL_NORM
    today = pd.Timestamp.today()
    annual = load_busan_annual_excel(data_dir)
    rows_excel: list[dict] = []
    if annual:
        for yr, annual_teu in sorted(annual.items()):
            if yr < start_year:
                continue
            monthly_avg_10k = annual_teu / 12 / 10_000
            for month in range(1, 13):
                dt = pd.Timestamp(yr, month, 1)
                if dt > today:
                    break
                rows_excel.append({
                    'date':       dt,
                    'throughput': round(monthly_avg_10k * _SEASONAL_NORM[month - 1], 2),
                })
    df_excel = pd.DataFrame(rows_excel) if rows_excel else None

    # 3순위: BPA API
    df_api = fetch_bpa_throughput(start_year=max(start_year, 2020))

    parts = [p for p in [df_excel, df_api] if p is not None and not p.empty]
    if not parts:
        logger.warning('부산항 물동량 모든 소스 실패')
        return None

    combined = (pd.concat(parts, ignore_index=True)
                .sort_values('date')
                .drop_duplicates('date', keep='last')
                .reset_index(drop=True))
    logger.info('부산항 물동량 통합(계절분배): %d개월 (%s ~ %s)',
                len(combined),
                combined['date'].iloc[0].strftime('%Y.%m'),
                combined['date'].iloc[-1].strftime('%Y.%m'))
    return combined


# ── ECOS 거시경제 API ─────────────────────────────────────────────────────────

def load_ecos(stat_code: str, item_code: str,
              start_ym: str, end_ym: str,
              cache_dir: Path | None = None) -> pd.DataFrame | None:
    """
    한국은행 ECOS API → DataFrame(date: datetime, value: float)
    API 키는 환경변수 ECOS_API_KEY에서 읽음.
    cache_dir 지정 시 CSV 캐시 사용.
    """
    api_key = os.environ.get('ECOS_API_KEY', '')
    if not api_key or api_key.startswith('여기에'):
        logger.info('ECOS_API_KEY 미설정 — 시뮬 폴백')
        return None

    cache_file: Path | None = None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f'{stat_code}_{item_code}_{start_ym}_{end_ym}.csv'
        if cache_file.exists():
            df = pd.read_csv(cache_file, encoding='utf-8-sig')
            df['date'] = pd.to_datetime(df['date'])
            return df

    url = (
        f'https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/1000'
        f'/{stat_code}/M/{start_ym}/{end_ym}/{item_code}'
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get('StatisticSearch', {}).get('row', [])
        if not rows:
            return None
        df = pd.DataFrame(rows)[['TIME', 'DATA_VALUE']].rename(
            columns={'TIME': 'date', 'DATA_VALUE': 'value'}
        )
        df['date']  = pd.to_datetime(df['date'].astype(str).str[:6], format='%Y%m')
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna().sort_values('date').reset_index(drop=True)
        if cache_file:
            df.to_csv(cache_file, index=False, encoding='utf-8-sig')
        return df
    except Exception as e:
        logger.warning('ECOS API 오류: %s', e)
        return None


# ── 유가 (Yahoo Finance 캐시 우선) ──────────────────────────────────────────

def load_oil_price(data_dir: Path, use_real: bool = True) -> pd.DataFrame | None:
    """
    Brent 유가 월별 로더.
    우선순위: ① ecos_cache/oil_monthly.csv (auto_update 일별 갱신본)
              ② Yahoo Finance 라이브 fetch
    반환: DataFrame(date: datetime, oil_price: float) or None
    """
    if not use_real:
        return None

    # 1순위: 캐시 CSV (auto_update.py --mode daily 실행 시 생성)
    cache_fp = data_dir / 'ecos_cache' / 'oil_monthly.csv'
    if cache_fp.exists():
        try:
            df = pd.read_csv(cache_fp, encoding='utf-8-sig')
            df['date']      = pd.to_datetime(df['date'], errors='coerce')
            df['oil_price'] = pd.to_numeric(df['oil_price'], errors='coerce')
            df = df.dropna().sort_values('date').reset_index(drop=True)
            if not df.empty:
                logger.info('유가 캐시 로드: %d개월 (최신 $%.1f)',
                            len(df), df['oil_price'].iloc[-1])
                return df
        except Exception:
            pass

    # 2순위: Yahoo Finance 라이브 (인터넷 필요)
    try:
        from src.real_data_fetcher import fetch_brent_oil_monthly
        df = fetch_brent_oil_monthly(start='2019-01-01')
        if df is not None:
            # 캐시 저장
            cache_fp.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_fp, index=False, encoding='utf-8-sig')
            logger.info('유가 라이브 수집 후 캐시 저장: %d개월', len(df))
            return df
    except Exception as e:
        logger.warning('유가 fetch 실패: %s', e)

    return None


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _read_csv_auto_enc(p: Path) -> pd.DataFrame | None:
    for enc in ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']:
        try:
            return pd.read_csv(p, encoding=enc)
        except (UnicodeDecodeError, Exception):
            continue
    logger.warning('%s 인코딩 감지 실패', p)
    return None


def _find_col(df: pd.DataFrame, keywords: list[str]) -> str | None:
    lower_cols = {c: c.lower() for c in df.columns}
    for kw in keywords:
        for col, col_l in lower_cols.items():
            if kw.lower() in col_l:
                return col
    return None
