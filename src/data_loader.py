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


# ── 부산항 2025 Excel + BPA API 결합 ─────────────────────────────────────────

def load_busan_2025_excel(data_dir: Path) -> dict | None:
    """
    '260414_홈페이지 업데이트_전국항 및 부산항 컨테이너 물동량' Excel에서
    2025년 부산항 연간 TEU 추출.
    반환: {'year': 2025, 'teu': float}  또는 None
    """
    # 파일명 패턴으로 탐색
    candidates = sorted(data_dir.glob('*컨테이너 물동량*.xlsx')) + \
                 sorted(data_dir.glob('*컨테이너*물동량*.xlsx'))
    if not candidates:
        logger.info('2025 물동량 Excel 없음')
        return None
    fp = candidates[-1]  # 가장 최신 파일
    try:
        df = pd.read_excel(fp, sheet_name=0, header=None)
        # 구조: 행0~3=헤더, 행4~=데이터 / 열0=연도, 열5=부산항 합계
        # 헤더 탐색 (연도 컬럼 위치 확인)
        year_col, busan_col = None, None
        for r in range(min(6, len(df))):
            row_vals = [str(v) for v in df.iloc[r].tolist()]
            if any('연도' in v for v in row_vals):
                year_col = next(i for i, v in enumerate(row_vals) if '연도' in v)
            if any('부산항' in v for v in row_vals):
                busan_col = next(i for i, v in enumerate(row_vals) if '부산항' in v)
        if year_col is None:
            year_col = 0   # 기본: 첫 번째 컬럼
        if busan_col is None:
            busan_col = 5  # 기본: 6번째 컬럼 (부산항 합계)

        records = {}
        for _, row in df.iterrows():
            try:
                yr  = int(float(str(row.iloc[year_col])))
                teu = float(str(row.iloc[busan_col]).replace(',', ''))
                if 2010 <= yr <= 2030 and teu > 1_000_000:
                    records[yr] = teu
            except (ValueError, TypeError):
                continue

        if 2025 in records:
            logger.info('Excel 2025 부산항: %.0f TEU (%.1f만/월평균)',
                        records[2025], records[2025]/12/10000)
            return {'year': 2025, 'teu': records[2025]}
        logger.warning('Excel에서 2025년 데이터 미발견')
        return None
    except Exception as e:
        logger.warning('Excel 파싱 오류: %s', e)
        return None


def load_busan_throughput_combined(data_dir: Path,
                                   start_year: int = 2020) -> pd.DataFrame | None:
    """
    부산항 월별 물동량 통합 로더.

    [데이터 소스]
    - 2020~2024: BPA 공공데이터포털 API (연도별 TEU + 계절 분해)
    - 2025:      수동 수집 Excel (BPA 홈페이지 업데이트 자료)
    양쪽 모두 계절 분해(seasonal decomposition) 적용.

    반환: DataFrame(date, throughput) 단위: 만 TEU/월
    """
    from src.real_data_fetcher import fetch_bpa_throughput, _SEASONAL_NORM
    import pandas as pd

    # 2020-2024: BPA API
    df_api = fetch_bpa_throughput(start_year=start_year)

    # 2025: Excel
    rec2025 = load_busan_2025_excel(data_dir)
    df_2025 = None
    if rec2025:
        today = pd.Timestamp.today()
        monthly_avg = rec2025['teu'] / 12 / 10_000
        rows = []
        for month in range(1, 13):
            dt = pd.Timestamp(2025, month, 1)
            if dt <= today:
                rows.append({'date': dt,
                             'throughput': round(monthly_avg * _SEASONAL_NORM[month-1], 2)})
        if rows:
            df_2025 = pd.DataFrame(rows)

    # 결합
    parts = [p for p in [df_api, df_2025] if p is not None and not p.empty]
    if not parts:
        logger.warning('BPA API + Excel 모두 실패 — 시뮬 폴백')
        return None

    combined = (pd.concat(parts, ignore_index=True)
                .sort_values('date')
                .drop_duplicates('date', keep='last')
                .reset_index(drop=True))
    logger.info('부산항 물동량 통합: %d개월 (%s ~ %s)',
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
