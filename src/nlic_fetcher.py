"""
nlic_fetcher.py — 국가물류통합정보센터(NLIC) 항만 물동량 수집기
https://nlic.go.kr/nlic/seaHarborGtqy.action

[자동 다운로드]
  - NLIC 사이트에 POST 요청으로 월별 Excel 다운로드 시도
  - 실패 시: data/nlic_raw/ 폴더의 수동 다운로드 파일 파싱

[수동 다운로드 방법]
  1. https://nlic.go.kr/nlic/seaHarborGtqy.action 접속
  2. 항만명: 부산 / 기간: 원하는 연월 선택
  3. Excel 다운로드
  4. data/nlic_raw/ 폴더에 저장
  5. combine_nlic_excels() 실행 → data/busan_throughput.csv 생성
"""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Referer': 'https://nlic.go.kr/nlic/seaHarborGtqy.action',
}
_BASE_URL = 'https://nlic.go.kr'
_TIMEOUT  = 30

# NLIC Excel 컬럼명 후보 (연도별로 헤더가 다를 수 있음)
_DATE_COLS      = ['기간', '연월', '년월', '날짜', '일자', 'date', '기준월', '조회기간']
_TEU_COLS       = ['컨테이너합계', '합계(TEU)', '합계', 'TEU합계', '컨테이너처리량',
                   '총합계', '컨테이너', 'total', 'teu']
_TEU_EXPORT     = ['컨테이너수출', '수출(TEU)', '수출컨테이너', '수출']
_TEU_IMPORT     = ['컨테이너수입', '수입(TEU)', '수입컨테이너', '수입']
_PORT_COL       = ['항만명', '항만', 'port', '지역']


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 자동 다운로드 (NLIC POST 요청)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_session_cookies() -> dict:
    """NLIC 메인 페이지 접속 → 세션 쿠키 획득."""
    try:
        sess = requests.Session()
        sess.get(f'{_BASE_URL}/nlic/seaHarborGtqy.action',
                 headers=_HEADERS, timeout=_TIMEOUT)
        return dict(sess.cookies)
    except Exception as e:
        logger.debug('NLIC 세션 쿠키 실패: %s', e)
        return {}


def download_nlic_month(year: int, month: int,
                        save_dir: Path) -> Path | None:
    """
    NLIC에서 특정 연월의 부산항 물동량 Excel 자동 다운로드.
    반환: 저장된 파일 경로 (실패 시 None)
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    ym      = f'{year}{month:02d}'
    out_fp  = save_dir / f'nlic_busan_{ym}.xlsx'

    if out_fp.exists():
        logger.info('이미 존재: %s', out_fp.name)
        return out_fp

    cookies = _get_session_cookies()

    # NLIC Excel 다운로드 엔드포인트 후보 (사이트 버전별 대응)
    endpoints = [
        '/nlic/excelDownload.do',
        '/nlic/seaHarborGtqy_excel.do',
        '/nlic/seaHarborExcelDown.action',
        '/nlic/excelDown.action',
    ]
    payloads = [
        # 형식 A: 연월 분리
        {'portNm': '부산', 'searchYear': str(year), 'searchMonth': f'{month:02d}',
         'startYm': ym, 'endYm': ym, 'dataType': '01', 'fileType': 'xlsx'},
        # 형식 B: 통합 연월
        {'portNm': '부산', 'searchYm': ym,
         'startYm': ym, 'endYm': ym, 'downType': 'excel'},
        # 형식 C: 간소화
        {'portNm': '부산', 'startYm': ym, 'endYm': ym},
    ]

    for endpoint in endpoints:
        for payload in payloads:
            try:
                url  = _BASE_URL + endpoint
                resp = requests.post(url, data=payload, cookies=cookies,
                                     headers=_HEADERS, timeout=_TIMEOUT)
                ct   = resp.headers.get('Content-Type', '')
                # Excel 파일인지 확인 (MIME type 또는 파일 시그니처)
                if (resp.status_code == 200
                        and len(resp.content) > 1000
                        and ('spreadsheet' in ct or 'excel' in ct or 'octet' in ct
                             or resp.content[:4] == b'PK\x03\x04')):  # XLSX 시그니처
                    out_fp.write_bytes(resp.content)
                    logger.info('NLIC 자동 다운로드 성공: %s (%s)', out_fp.name, endpoint)
                    return out_fp
            except Exception as e:
                logger.debug('NLIC %s 실패: %s', endpoint, e)

    logger.warning('NLIC 자동 다운로드 실패: %d년 %d월', year, month)
    return None


def download_nlic_range(start_ym: str = '201501',
                        end_ym: str | None = None,
                        save_dir: Path | None = None) -> list[Path]:
    """
    start_ym ~ end_ym 범위의 NLIC 데이터를 월별 자동 다운로드.
    반환: 성공적으로 저장된 파일 경로 목록
    """
    if end_ym is None:
        end_ym = datetime.today().strftime('%Y%m')
    if save_dir is None:
        save_dir = Path('data') / 'nlic_raw'

    sy, sm = int(start_ym[:4]), int(start_ym[4:6])
    ey, em = int(end_ym[:4]),   int(end_ym[4:6])

    saved: list[Path] = []
    cur_y, cur_m = sy, sm
    total = (ey - sy) * 12 + (em - sm) + 1
    done  = 0

    print(f'NLIC 자동 다운로드: {start_ym} ~ {end_ym} ({total}개월)')
    while (cur_y, cur_m) <= (ey, em):
        fp = download_nlic_month(cur_y, cur_m, save_dir)
        if fp:
            saved.append(fp)
        done += 1
        if done % 12 == 0:
            print(f'  진행: {done}/{total}개월 완료')
        time.sleep(0.5)   # 서버 부하 방지

        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1

    print(f'완료: {len(saved)}/{total}개월 다운로드 성공')
    return saved


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Excel 파싱 (자동 + 수동 다운로드 공통)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """DataFrame에서 후보 컬럼명 중 실제로 존재하는 것 반환."""
    cols_lower = {c.lower().replace(' ', '').replace('(', '').replace(')', ''): c
                  for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace(' ', '').replace('(', '').replace(')', '')
        if key in cols_lower:
            return cols_lower[key]
    return None


def parse_nlic_excel(fp: Path) -> pd.DataFrame | None:
    """
    NLIC Excel 파일 1개 → DataFrame(date, throughput) 변환.
    단위: 만 TEU

    NLIC Excel 형식 (2015~2026):
    - 헤더가 여러 행일 수 있음 → 자동 탐색
    - 컬럼명이 연도별로 다를 수 있음 → 후보 목록으로 자동 매핑
    - 부산항만 필터링
    """
    try:
        # 헤더 위치 자동 탐색 (상위 10행 검사)
        for skip in range(10):
            try:
                df = pd.read_excel(fp, skiprows=skip, dtype=str)
                df.columns = [str(c).strip() for c in df.columns]
                # 유효한 데이터 행이 5개 이상이면 헤더 찾은 것
                if len(df.dropna(how='all')) >= 5:
                    break
            except Exception:
                continue
        else:
            logger.warning('헤더 탐색 실패: %s', fp.name)
            return None

        # 빈 행 제거
        df = df.dropna(how='all').reset_index(drop=True)

        # 날짜 컬럼 탐색
        date_col = _find_col(df, _DATE_COLS)
        if date_col is None:
            # 첫 번째 컬럼을 날짜로 간주
            date_col = df.columns[0]

        # TEU 합계 컬럼 탐색 (수출+수입+연안 합계 우선)
        teu_col = _find_col(df, _TEU_COLS)
        if teu_col is None:
            # 수출+수입 합산으로 계산
            exp_col = _find_col(df, _TEU_EXPORT)
            imp_col = _find_col(df, _TEU_IMPORT)
            if exp_col and imp_col:
                df['_total'] = (pd.to_numeric(df[exp_col].str.replace(',', ''), errors='coerce').fillna(0)
                                + pd.to_numeric(df[imp_col].str.replace(',', ''), errors='coerce').fillna(0))
                teu_col = '_total'
            else:
                # 숫자가 가장 큰 컬럼 선택 (TEU 합계일 가능성 높음)
                num_cols = [c for c in df.columns if c != date_col]
                num_means = {}
                for c in num_cols:
                    vals = pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce')
                    if vals.notna().sum() > 3:
                        num_means[c] = vals.mean()
                if num_means:
                    teu_col = max(num_means, key=num_means.get)
                else:
                    logger.warning('TEU 컬럼 탐색 실패: %s', fp.name)
                    return None

        # 항만명 필터 (부산만 추출)
        port_col = _find_col(df, _PORT_COL)
        if port_col:
            busan_mask = df[port_col].astype(str).str.contains('부산', na=False)
            df = df[busan_mask]

        # 날짜 파싱
        dates = _parse_date_series(df[date_col])

        # TEU 파싱 → 만 TEU 단위 변환
        teus = pd.to_numeric(
            df[teu_col].astype(str).str.replace(',', '').str.strip(),
            errors='coerce'
        )

        result = pd.DataFrame({'date': dates, 'throughput': teus}).dropna()

        # 단위 자동 변환 (만 TEU 기준)
        mean_val = result['throughput'].mean()
        if mean_val > 500_000:          # 단위: TEU
            result['throughput'] /= 10_000
        elif mean_val > 50_000:         # 단위: 천 TEU 또는 백 TEU
            result['throughput'] /= 1_000
        elif mean_val > 5_000:
            result['throughput'] /= 100

        result = result.sort_values('date').reset_index(drop=True)
        logger.info('파싱 성공: %s → %d행', fp.name, len(result))
        return result

    except Exception as e:
        logger.warning('Excel 파싱 실패 (%s): %s', fp.name, e)
        return None


def _parse_date_series(series: pd.Series) -> pd.Series:
    """다양한 날짜 형식 → datetime 변환."""
    results = []
    for val in series:
        s   = str(val).strip()
        dt  = None
        # 패턴: "2015년 1월", "2015.01", "201501", "2015-01", "2015/01"
        for pat in [
            (r'^(\d{4})년\s*(\d{1,2})월', lambda m: f'{m.group(1)}-{int(m.group(2)):02d}-01'),
            (r'^(\d{4})[.\-/](\d{1,2})$', lambda m: f'{m.group(1)}-{int(m.group(2)):02d}-01'),
            (r'^(\d{6})$',                 lambda m: f'{m.group(1)[:4]}-{m.group(1)[4:6]}-01'),
            (r'^(\d{4})$',                 lambda m: f'{m.group(1)}-01-01'),
        ]:
            match = re.match(pat[0], s)
            if match:
                try:
                    dt = pd.to_datetime(pat[1](match))
                    break
                except Exception:
                    pass
        if dt is None:
            try:
                dt = pd.to_datetime(s, errors='coerce')
            except Exception:
                dt = pd.NaT
        results.append(dt)
    return pd.Series(results)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 파일 합치기
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def combine_nlic_excels(raw_dir: Path | None = None,
                        out_csv: Path | None = None) -> pd.DataFrame | None:
    """
    raw_dir 안의 NLIC Excel 파일 전부를 파싱하여 하나의 CSV로 합침.
    반환: 합쳐진 DataFrame(date, throughput) 또는 None
    """
    if raw_dir is None:
        raw_dir = Path('data') / 'nlic_raw'
    if out_csv is None:
        out_csv = Path('data') / 'busan_throughput.csv'

    excel_files = sorted(
        list(raw_dir.glob('*.xlsx')) + list(raw_dir.glob('*.xls'))
    )
    if not excel_files:
        logger.warning('NLIC Excel 파일 없음: %s', raw_dir)
        print(f'⚠️  {raw_dir} 폴더에 Excel 파일이 없습니다.')
        print('   아래 방법으로 파일을 저장한 후 다시 실행하세요:')
        print('   1. https://nlic.go.kr/nlic/seaHarborGtqy.action 접속')
        print('   2. 항만명=부산, 기간 선택 → Excel 다운로드')
        print(f'   3. 파일을 {raw_dir}/ 폴더에 저장')
        return None

    frames: list[pd.DataFrame] = []
    for fp in excel_files:
        df = parse_nlic_excel(fp)
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        logger.warning('파싱된 데이터 없음')
        return None

    combined = (pd.concat(frames, ignore_index=True)
                .drop_duplicates(subset='date')
                .sort_values('date')
                .reset_index(drop=True))

    # 월 단위 정규화
    combined['date'] = combined['date'].dt.to_period('M').dt.to_timestamp()

    # 저장
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_csv, index=False, encoding='utf-8-sig')

    print(f'✅ NLIC 데이터 합치기 완료')
    print(f'   기간: {combined["date"].min().strftime("%Y.%m")} ~ '
          f'{combined["date"].max().strftime("%Y.%m")}')
    print(f'   행수: {len(combined)}개월')
    print(f'   평균: {combined["throughput"].mean():.1f}만 TEU/월')
    print(f'   저장: {out_csv}')
    return combined


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 메인 로더 (data_loader.py 대체재)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_nlic_throughput(data_dir: Path | None = None) -> pd.DataFrame | None:
    """
    NLIC 물동량 데이터 로더.
    우선순위: 합쳐진 CSV → NLIC 자동 다운로드 후 합치기 → None(시뮬 폴백)

    반환: DataFrame(date, throughput) 또는 None
    """
    if data_dir is None:
        data_dir = Path('data')

    csv_fp  = data_dir / 'busan_throughput.csv'
    raw_dir = data_dir / 'nlic_raw'

    # 1순위: 이미 합쳐진 CSV
    if csv_fp.exists():
        try:
            df = pd.read_csv(csv_fp, encoding='utf-8-sig')
            df['date']       = pd.to_datetime(df['date'])
            df['throughput'] = pd.to_numeric(df['throughput'], errors='coerce')
            df = df.dropna().sort_values('date').reset_index(drop=True)
            logger.info('NLIC CSV 로드: %d개월', len(df))
            return df
        except Exception as e:
            logger.warning('CSV 로드 실패: %s', e)

    # 2순위: raw_dir에 Excel 있으면 합치기
    if raw_dir.exists() and any(raw_dir.glob('*.xls*')):
        df = combine_nlic_excels(raw_dir, csv_fp)
        if df is not None:
            return df

    # 3순위: 자동 다운로드 시도 (최근 6개월만)
    logger.info('NLIC 자동 다운로드 시도 (최근 6개월)...')
    today   = datetime.today()
    start_y = today.year - (1 if today.month <= 6 else 0)
    start_m = (today.month - 6) % 12 or 12
    fps     = download_nlic_range(
        f'{start_y}{start_m:02d}',
        today.strftime('%Y%m'),
        save_dir=raw_dir,
    )
    if fps:
        df = combine_nlic_excels(raw_dir, csv_fp)
        if df is not None:
            return df

    return None
