"""
freight_index_loader.py — KCCI / KUWI / KUEI 등 운임지수 XLS 파서

[지원 파일]
  data/freight_index/*.xls, *.xlsx
  한국해운거래소·한국해운신문 발간 주간 운임지수 파일

[인식하는 지수]
  KCCI  한국컨테이너운임종합지수
  KUWI  한국컨테이너운임가중지수  (있으면)
  KUEI  한국컨테이너운임등락지수  (있으면)
  + 항로별 세부 지수 (부산-LA, 부산-로테르담 등)

[반환 형식]
  DataFrame(date, kcci, kuwi, kuei, ...)   — 주별 (Weekly)
  또는 load_kcci_weekly() → DataFrame(date, value)  ← mri_engine용 호환
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 컬럼명 키워드 매핑
_IDX_KEYWORDS: dict[str, list[str]] = {
    'kcci': ['kcci', '종합지수', '컨테이너종합', 'composite'],
    'kuwi': ['kuwi', '가중지수', '가중운임'],
    'kuei': ['kuei', '등락지수', '등락운임'],
    'busan_la':  ['부산-la', '부산la', '부산/la', '미서안', 'us west'],
    'busan_eu':  ['부산-로테', '부산로테', '로테르담', 'rotterdam', '유럽'],
    'busan_sh':  ['부산-상하이', '부산상하이', '상해', 'shanghai'],
    'busan_sg':  ['부산-싱가', '싱가포르', 'singapore'],
    'busan_jp':  ['부산-도쿄', '일본', 'japan', 'tokyo'],
}
_DATE_KEYWORDS = ['발표일', '기준일', '날짜', '일자', '주', 'date', '기준']


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 단일 XLS 파일 파싱
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _read_xls(fp: Path) -> pd.DataFrame | None:
    """XLS/XLSX 파일 읽기 — 헤더 위치 자동 탐색."""
    ext    = fp.suffix.lower()
    engine = 'xlrd' if ext == '.xls' else 'openpyxl'

    # 시트 목록 탐색
    try:
        xl = pd.ExcelFile(fp, engine=engine)
        sheets = xl.sheet_names
    except Exception as e:
        logger.warning('ExcelFile 열기 실패 (%s): %s', fp.name, e)
        return None

    best_df: pd.DataFrame | None = None
    best_score = 0

    for sheet in sheets:
        for skip in range(8):   # 헤더가 최대 7행 아래에 있을 수 있음
            try:
                df = pd.read_excel(fp, sheet_name=sheet, skiprows=skip,
                                   engine=engine, dtype=str, header=0)
                df.columns = [str(c).strip() for c in df.columns]
                df = df.dropna(how='all').reset_index(drop=True)

                # 유효성 점수: 날짜 컬럼 + 지수 컬럼 개수
                score = _score_df(df)
                if score > best_score:
                    best_score = score
                    best_df    = df.copy()
                if score >= 3:   # 충분히 좋은 헤더 발견
                    break
            except Exception:
                continue

    if best_df is None or best_score == 0:
        logger.warning('파싱 실패 (유효 헤더 없음): %s', fp.name)
        return None
    return best_df


def _score_df(df: pd.DataFrame) -> int:
    """컬럼명 품질 점수 (날짜 컬럼 + 지수 컬럼 수)."""
    cols_l = [c.lower().replace(' ', '') for c in df.columns]
    score  = 0
    for kw in _DATE_KEYWORDS:
        if any(kw in c for c in cols_l):
            score += 2
            break
    for idx_kws in _IDX_KEYWORDS.values():
        if any(any(kw in c for kw in idx_kws) for c in cols_l):
            score += 1
    return score


def _map_columns(df: pd.DataFrame) -> dict[str, str]:
    """원본 컬럼명 → 표준 키 매핑."""
    mapping: dict[str, str] = {}
    cols_l = {c: c.lower().replace(' ', '').replace('-', '').replace('/', '')
              for c in df.columns}

    # 날짜 컬럼
    for col, col_l in cols_l.items():
        if any(kw.replace('-', '').replace('/', '') in col_l for kw in _DATE_KEYWORDS):
            if 'date' not in mapping.values():
                mapping[col] = 'date'
                break

    # 지수 컬럼
    for std_key, kws in _IDX_KEYWORDS.items():
        for col, col_l in cols_l.items():
            if col in mapping:
                continue
            if any(kw.replace('-', '').replace('/', '') in col_l for kw in kws):
                mapping[col] = std_key
                break

    return mapping


def _parse_date(series: pd.Series) -> pd.Series:
    """다양한 날짜 문자열 → datetime."""
    results = []
    for raw in series:
        s  = str(raw).strip()
        dt = pd.NaT

        # 패턴 시도
        patterns = [
            r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})',   # 2022.11.07
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',    # 2022년11월7일
            r'(\d{4})(\d{2})(\d{2})',                     # 20221107
            r'(\d{4})[.\-/](\d{1,2})',                    # 2022.11
            r'(\d{4})(\d{2})',                             # 202211
        ]
        for pat in patterns:
            m = re.search(pat, s)
            if m:
                groups = m.groups()
                try:
                    if len(groups) == 3:
                        dt = pd.Timestamp(int(groups[0]), int(groups[1]), int(groups[2]))
                    elif len(groups) == 2:
                        dt = pd.Timestamp(int(groups[0]), int(groups[1]), 1)
                    break
                except Exception:
                    continue

        if pd.isna(dt):
            try:
                dt = pd.to_datetime(s, errors='coerce')
            except Exception:
                dt = pd.NaT

        results.append(dt)
    return pd.Series(results)


def parse_freight_excel(fp: Path) -> pd.DataFrame | None:
    """
    XLS/XLSX 파일 1개 → 표준 DataFrame 변환.
    반환: DataFrame(date, kcci, kuwi, kuei, ...) 또는 None
    """
    raw = _read_xls(fp)
    if raw is None:
        return None

    col_map = _map_columns(raw)
    if 'date' not in col_map.values():
        logger.warning('날짜 컬럼 없음: %s (컬럼: %s)', fp.name, list(raw.columns[:8]))
        return None

    has_any_index = any(v != 'date' for v in col_map.values())
    if not has_any_index:
        logger.warning('지수 컬럼 없음: %s', fp.name)
        return None

    # 표준 컬럼만 선택
    inv_map = {v: k for k, v in col_map.items()}   # std_key → 원본컬럼
    cols_to_use = {orig: std for orig, std in col_map.items()}
    df_sub = raw[list(cols_to_use.keys())].rename(columns=cols_to_use).copy()

    # 날짜 파싱
    df_sub['date'] = _parse_date(df_sub['date'])

    # 지수값 → 숫자 변환
    for col in df_sub.columns:
        if col == 'date':
            continue
        df_sub[col] = pd.to_numeric(
            df_sub[col].astype(str).str.replace(',', '').str.strip(),
            errors='coerce'
        )

    df_sub = df_sub.dropna(subset=['date']).sort_values('date').reset_index(drop=True)

    # 날짜를 주 시작일(월요일)로 정규화
    df_sub['date'] = df_sub['date'] - pd.to_timedelta(df_sub['date'].dt.dayofweek, unit='D')

    logger.info('파싱 성공: %s → %d행, 컬럼: %s',
                fp.name, len(df_sub), [c for c in df_sub.columns if c != 'date'])
    return df_sub


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 여러 파일 합치기
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def combine_freight_excels(
    raw_dir: Path | None = None,
    out_csv: Path | None = None,
) -> pd.DataFrame | None:
    """
    raw_dir 안의 모든 XLS/XLSX 파일을 파싱·합쳐서 CSV로 저장.
    반환: DataFrame(date, kcci, kuwi, kuei, ...) 주별 정렬
    """
    if raw_dir is None:
        raw_dir = Path('data') / 'freight_index'
    if out_csv is None:
        out_csv = Path('data') / 'kcci_weekly.csv'

    files = sorted(
        list(raw_dir.glob('*.xls')) + list(raw_dir.glob('*.xlsx'))
    )
    if not files:
        logger.warning('XLS 파일 없음: %s', raw_dir)
        return None

    frames: list[pd.DataFrame] = []
    for fp in files:
        df = parse_freight_excel(fp)
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        return None

    combined = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset='date')
        .sort_values('date')
        .reset_index(drop=True)
    )

    # 결측 지수 행 제거 (모든 지수가 NaN인 행)
    idx_cols = [c for c in combined.columns if c != 'date']
    combined = combined.dropna(subset=idx_cols, how='all').reset_index(drop=True)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_csv, index=False, encoding='utf-8-sig')

    print(f'✅ 운임지수 합치기 완료')
    print(f'   기간: {combined["date"].min().strftime("%Y.%m.%d")} ~ '
          f'{combined["date"].max().strftime("%Y.%m.%d")}')
    print(f'   주수: {len(combined)}주')
    print(f'   지수: {idx_cols}')
    print(f'   저장: {out_csv}')
    return combined


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 메인 로더 (mri_engine 호환 인터페이스)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_kcci_weekly(data_dir: Path | None = None) -> pd.DataFrame | None:
    """
    KCCI 주간 데이터 로더 (mri_engine.py 호환).
    반환: DataFrame(date, value) — value = KCCI 종합지수
    data_loader.load_kcci()의 대체재.
    """
    if data_dir is None:
        data_dir = Path('data')

    csv_fp  = data_dir / 'kcci_weekly.csv'
    raw_dir = data_dir / 'freight_index'

    # 1순위: 이미 합쳐진 CSV
    if csv_fp.exists():
        try:
            df = pd.read_csv(csv_fp, encoding='utf-8-sig')
            df['date'] = pd.to_datetime(df['date'])
            if 'kcci' in df.columns:
                result = df[['date', 'kcci']].rename(columns={'kcci': 'value'}).dropna()
                logger.info('KCCI 주간 CSV 로드: %d주', len(result))
                return result.sort_values('date').reset_index(drop=True)
        except Exception as e:
            logger.warning('KCCI CSV 로드 실패: %s', e)

    # 2순위: raw_dir에 XLS 있으면 합치기
    if raw_dir.exists() and any(raw_dir.glob('*.xls*')):
        df = combine_freight_excels(raw_dir, csv_fp)
        if df is not None and 'kcci' in df.columns:
            return df[['date', 'kcci']].rename(columns={'kcci': 'value'}).dropna()

    return None


def load_all_indices(data_dir: Path | None = None) -> pd.DataFrame | None:
    """
    전체 운임지수 로더 (KCCI + KUWI + KUEI + 항로별).
    반환: DataFrame(date, kcci, kuwi, kuei, ...) 또는 None
    """
    if data_dir is None:
        data_dir = Path('data')

    csv_fp  = data_dir / 'kcci_weekly.csv'
    raw_dir = data_dir / 'freight_index'

    if csv_fp.exists():
        try:
            df = pd.read_csv(csv_fp, encoding='utf-8-sig')
            df['date'] = pd.to_datetime(df['date'])
            return df.sort_values('date').reset_index(drop=True)
        except Exception as e:
            logger.warning('운임지수 CSV 로드 실패: %s', e)

    if raw_dir.exists() and any(raw_dir.glob('*.xls*')):
        return combine_freight_excels(raw_dir, csv_fp)

    return None
