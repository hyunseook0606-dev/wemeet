"""
real_data_fetcher.py — 실데이터 수집 모듈

키 불필요 (즉시 사용):
  - 해사 뉴스 RSS : gCaptain / Splash247 / 한국해운신문
  - USD/KRW 환율  : frankfurter.app
  - Brent 유가    : stooq.com

환경변수 설정 후 사용:
  - ECOS_API_KEY  : 한국은행 ECOS (환율·유가·GDP 공식)
  - BPA_API_KEY   : 부산항만공사 컨테이너 수송통계 (연도별)
  - DATA_GO_KR_KEY: KCCI 한국형 컨테이너 운임지수
"""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta
from io import StringIO

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 Chrome/124.0 Safari/537.36'
    )
}
_TIMEOUT = 15


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 해사 뉴스 RSS (키 불필요)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RSS_SOURCES = {
    'gCaptain':     'https://feeds.feedburner.com/gcaptain',
    'Splash247':    'https://splash247.com/feed/',
    '한국해운신문': 'http://www.maritimepress.co.kr/rss/allArticle.xml',
}


def fetch_maritime_news(max_per_source: int = 30,
                        days_back: int = 30) -> pd.DataFrame:
    """
    3개 RSS 소스에서 해사 뉴스를 수집.
    반환: DataFrame(title, text, pub_date, source)
    """
    try:
        import feedparser
    except ImportError:
        logger.warning('feedparser 미설치 — pip install feedparser')
        return pd.DataFrame(columns=['title', 'text', 'pub_date', 'source'])

    cutoff  = datetime.utcnow() - timedelta(days=days_back)
    records: list[dict] = []

    for source, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_source]:
                pub = _parse_rss_date(entry)
                if pub and pub < cutoff:
                    continue
                summary = entry.get('summary', entry.get('description', ''))
                clean   = re.sub(r'<[^>]+>', ' ', summary).strip()
                records.append({
                    'title':    entry.get('title', ''),
                    'text':     clean[:500],
                    'pub_date': pub.strftime('%Y-%m-%d') if pub else '',
                    'source':   source,
                    'url':      entry.get('link', ''),
                })
            logger.info('%s: %d건', source, len(feed.entries))
        except Exception as e:
            logger.warning('%s RSS 실패: %s', source, e)

    return pd.DataFrame(records) if records else pd.DataFrame(
        columns=['title', 'text', 'pub_date', 'source', 'url']
    )


# ── MRI 차원 태그 매핑 ────────────────────────────────────────────────────────
_DIM_KEYWORDS: dict[str, list[str]] = {
    'G': [
        'blockade', 'war', 'conflict', 'attack', 'houthi', 'iran', 'russia',
        'missile', 'tension', 'hormuz', 'red sea', 'strait', 'military',
        'seizure', 'naval', 'piracy', 'drone', 'sanctions',
        '봉쇄', '전쟁', '분쟁', '공격', '후티', '이란', '러시아', '미사일',
        '긴장', '호르무즈', '홍해', '해협', '군사', '위협',
    ],
    'D': [
        'typhoon', 'storm', 'flood', 'earthquake', 'weather', 'cyclone',
        'hurricane', 'disruption', 'delay', 'divert', 'reroute', 'canal',
        '태풍', '폭풍', '홍수', '지진', '기상', '결항', '지연', '우회',
    ],
    'F': [
        'freight rate', 'scfi', 'kcci', 'bdi', 'freight index', 'surge',
        'rate hike', 'spot rate', 'bunker', 'surcharge', 'gri',
        'blank sailing', 'capacity', 'shortage',
        '운임', '급등', '운임지수', '선복', '부족', '인상', '할증',
    ],
    'P': [
        'tariff', 'sanction', 'trade war', 'embargo', 'ban', 'customs',
        'strike', 'labor', 'union', 'walkout', 'port congestion',
        '관세', '제재', '무역전쟁', '파업', '노조', '항만혼잡', '금지',
    ],
}


def get_maritime_news_feed(
    top_n:       int = 10,
    days_back:   int = 7,
) -> list[dict]:
    """
    최근 해사 뉴스 피드 — MRI 차원 태그·키워드 포함.

    반환: list of dict {
        'title'       : 기사 제목,
        'source'      : 언론사,
        'pub_date'    : 발행일 (YYYY-MM-DD),
        'url'         : 원문 링크,
        'dim_tags'    : list[str]  예: ['G', 'F'],
        'keywords'    : list[str]  매칭된 키워드 (최대 3개),
    }
    정렬: 최신순, 리스크 관련 기사 우선
    """
    df = fetch_maritime_news(max_per_source=30, days_back=days_back)
    if df.empty:
        return []

    results = []
    for _, row in df.iterrows():
        combined = (str(row.get('title', '')) + ' ' +
                    str(row.get('text', ''))).lower()

        dim_tags: list[str] = []
        keywords: list[str] = []
        for dim, kws in _DIM_KEYWORDS.items():
            matched = [kw for kw in kws if kw.lower() in combined]
            if matched:
                dim_tags.append(dim)
                keywords.extend(matched[:2])   # 차원당 최대 2개

        if not dim_tags:
            continue    # 해사 리스크 무관 기사 제외

        keywords = list(dict.fromkeys(keywords))[:3]   # 중복 제거, 최대 3개
        results.append({
            'title':    row.get('title', '').strip(),
            'source':   row.get('source', ''),
            'pub_date': row.get('pub_date', ''),
            'url':      row.get('url', ''),
            'dim_tags': sorted(set(dim_tags)),
            'keywords': keywords,
        })

    # 최신순 정렬 후 상위 top_n
    results.sort(key=lambda x: x['pub_date'], reverse=True)
    return results[:top_n]


def _parse_rss_date(entry) -> datetime | None:
    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6])
            except Exception:
                pass
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. USD/KRW 환율 — frankfurter.app (키 불필요)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_exchange_rate_monthly(start: str = '2020-01-01',
                                end: str | None = None) -> pd.DataFrame | None:
    """
    frankfurter.app → USD/KRW 월별 평균 환율.
    반환: DataFrame(date, exchange_rate)
    """
    if end is None:
        end = datetime.today().strftime('%Y-%m-%d')
    url = f'https://api.frankfurter.app/{start}..{end}?from=USD&to=KRW'
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        rows = [
            {'date': datetime.strptime(d, '%Y-%m-%d'), 'exchange_rate': v['KRW']}
            for d, v in resp.json().get('rates', {}).items()
        ]
        if not rows:
            return None
        df = (pd.DataFrame(rows)
              .sort_values('date')
              .set_index('date')['exchange_rate']
              .resample('MS').mean()
              .reset_index())
        logger.info('USD/KRW 환율: %d개월', len(df))
        return df
    except Exception as e:
        logger.warning('frankfurter.app 환율 실패: %s', e)
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Brent 유가 — stooq.com (키 불필요)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_brent_oil_monthly(start: str = '2020-01-01') -> pd.DataFrame | None:
    """
    Brent 원유 월별 평균 (USD/배럴).
    1순위: Yahoo Finance (BZ=F 선물, 무료·키 불필요, 안정적)
    2순위: FRED MCOILBRENTEU (월평균, 무료·키 불필요)
    3순위: EIA (미국 에너지청, DEMO 키, 5000req/일)
    반환: DataFrame(date, oil_price)
    """
    start_dt = pd.to_datetime(start)

    # 1순위: Yahoo Finance BZ=F (Brent 선물, 월봉)
    try:
        url  = 'https://query1.finance.yahoo.com/v8/finance/chart/BZ%3DF?range=10y&interval=1mo'
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        result = resp.json().get('chart', {}).get('result', [])
        if result:
            ts     = result[0].get('timestamp', [])
            closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
            rows   = []
            for t, c in zip(ts, closes):
                if c is not None:
                    # Unix timestamp → UTC 날짜, 월 첫째날로 정규화
                    dt = pd.to_datetime(t, unit='s', utc=True).normalize().replace(day=1).tz_localize(None)
                    rows.append({'date': dt, 'oil_price': round(float(c), 2)})
            if rows:
                df = (pd.DataFrame(rows)
                      .sort_values('date')
                      .drop_duplicates('date', keep='last')
                      .reset_index(drop=True))
                df = df[df['date'] >= start_dt].reset_index(drop=True)
                if len(df) > 0:
                    logger.info('Yahoo Finance Brent 유가: %d개월', len(df))
                    return df
    except Exception as e:
        logger.debug('Yahoo Finance Brent 실패: %s', e)

    # 2순위: FRED MCOILBRENTEU (월평균)
    try:
        url  = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=MCOILBRENTEU'
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        # 컬럼: observation_date, MCOILBRENTEU
        df.columns = ['date', 'oil_price']
        df['date']      = pd.to_datetime(df['date'], errors='coerce')
        df['oil_price'] = pd.to_numeric(df['oil_price'], errors='coerce')
        df = (df.dropna()
                .sort_values('date'))
        df = df[df['date'] >= start_dt].reset_index(drop=True)
        if len(df) > 0:
            logger.info('FRED Brent 유가: %d개월', len(df))
            return df
    except Exception as e:
        logger.debug('FRED Brent 실패: %s', e)

    # 3순위: EIA (미국 에너지청, DEMO 키 — 하루 5000 요청 무료)
    try:
        url = ('https://api.eia.gov/v2/petroleum/pri/spt/data/'
               '?api_key=DEMO&frequency=monthly&data[0]=value'
               '&facets[product][]=EPCBRENT&sort[0][column]=period'
               '&sort[0][direction]=desc&offset=0&length=120')
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        rows = resp.json().get('response', {}).get('data', [])
        if rows:
            df = pd.DataFrame(rows)[['period', 'value']].rename(
                columns={'period': 'date', 'value': 'oil_price'}
            )
            df['date']      = pd.to_datetime(df['date'], errors='coerce')
            df['oil_price'] = pd.to_numeric(df['oil_price'], errors='coerce')
            df = (df.dropna()
                    .sort_values('date'))
            df = df[df['date'] >= start_dt].reset_index(drop=True)
            if len(df) > 0:
                logger.info('EIA Brent 유가: %d개월', len(df))
                return df
    except Exception as e:
        logger.debug('EIA Brent 실패: %s', e)

    logger.warning('Brent 유가 모든 소스 실패 (Yahoo/FRED/EIA) — 시뮬 폴백')
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 부산항만공사 컨테이너 수송통계 (연도별 → 월별 변환)
#    환경변수: BPA_API_KEY
#    데이터셋: 15055478 (1994~2024 연도별 TEU)
#    월별 API 없음 → 연도별 합계 + 계절 분해로 월별 추정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 부산항 월별 계절 가중치 (실제 부산항 패턴 기반)
# 근거: 설 연휴(1~2월) 저점, 연말 성수기(11~12월) 고점
# 정규화: 합계 = 12 (연간 합계 = 연평균 × 12)
_BUSAN_SEASONAL = [0.84, 0.76, 0.87, 0.92, 0.96, 1.00,
                   1.02, 1.03, 0.99, 1.06, 1.08, 1.12]
_SEASONAL_NORM  = [w * 12 / sum(_BUSAN_SEASONAL) for w in _BUSAN_SEASONAL]

# 확인된 엔드포인트 (2024-05 검증)
# EP6: 1994~2024 (31개년, 가장 최신) — 주 사용
# EP5: 1993~2023 (31개년) — 백업
_BPA_EP6 = 'https://api.odcloud.kr/api/15055478/v1/uddi:80709ec8-4d80-4407-8cc8-fafbea21766a'
_BPA_EP5 = 'https://api.odcloud.kr/api/15055478/v1/uddi:6668fa12-2691-47d4-9e1c-d6e415c6fc52'
_BPA_EP4 = 'https://api.odcloud.kr/api/15055478/v1/uddi:efd6b404-4425-452f-a9db-a38436ee59b9'
_BPA_EP3 = 'https://api.odcloud.kr/api/15055478/v1/uddi:57d4ac51-57f4-460d-878a-8f8884deb2d6'


def fetch_bpa_throughput(start_year: int = 2020) -> pd.DataFrame | None:
    """
    공공데이터포털 BPA API → 부산항 컨테이너 연도별 수송통계.
    연도별 합계 TEU를 계절 분해하여 월별 추정치로 반환.

    [방법론]
    BPA API는 월별 제공 없음. 연도별 합계(TEU)에 부산항 실제
    계절 패턴(1~12월 가중치)을 적용해 월별을 추정합니다.
    예) 2024년 합계 24,402,022 TEU → 월평균 203.4만 TEU
        1월: 203.4 × 0.866 = 176.1만 (설 연휴 저점)
       12월: 203.4 × 1.153 = 234.5만 (연말 성수기)

    반환: DataFrame(date, throughput)  단위: 만 TEU/월
    환경변수: BPA_API_KEY
    """
    api_key = os.environ.get('BPA_API_KEY', '')
    if not api_key:
        logger.info('BPA_API_KEY 미설정 — 시뮬 폴백')
        return None

    # 엔드포인트별 컬럼명 명시 (자동 감지 대신 직접 지정 — 안정성 우선)
    # EP6: 1994~2024 (가장 최신), 년도/합계 컬럼
    # EP5: 1993~2023 (백업),       연도/전체 컬럼
    ep_configs = [
        (_BPA_EP6, '년도', '합계'),
        (_BPA_EP5, '연도', '전체'),
        (_BPA_EP4, '연도', '전체'),
        (_BPA_EP3, '연도', '전체'),
    ]
    yearly_records: list[dict] = []

    for url, year_col, total_col in ep_configs:
        try:
            resp = requests.get(url,
                                params={'serviceKey': api_key, 'page': 1, 'perPage': 100},
                                headers=_HEADERS, timeout=30)
            if resp.status_code != 200:
                logger.debug('BPA EP 응답 %d (%s)', resp.status_code, url[-8:])
                continue
            rows = resp.json().get('data', [])
            if not rows:
                logger.debug('BPA EP 데이터 없음 (%s)', url[-8:])
                continue
            if year_col not in rows[0] or total_col not in rows[0]:
                logger.debug('BPA EP 컬럼 불일치 (%s): %s', url[-8:], list(rows[0].keys())[:5])
                continue
            recs = []
            for row in rows:
                try:
                    recs.append({
                        'year': int(row[year_col]),
                        'teu':  float(str(row[total_col]).replace(',', '')),
                    })
                except (ValueError, TypeError):
                    continue
            if recs:
                yearly_records = recs
                logger.info('BPA API 연결 성공 (%d개년, %d~%d)',
                            len(recs),
                            min(r['year'] for r in recs),
                            max(r['year'] for r in recs))
                break
        except Exception as e:
            logger.debug('BPA EP 예외 (%s): %s', url[-8:], e)

    if not yearly_records:
        logger.warning('BPA API 실패 — data/busan_throughput.csv 수동 다운로드 필요')
        return None

    # 연도별 → 월별 계절 분해
    monthly_records: list[dict] = []
    today = pd.Timestamp.today()

    for rec in sorted(yearly_records, key=lambda x: x['year']):
        year      = rec['year']
        total_teu = rec['teu']          # TEU 단위
        if year < start_year:
            continue
        monthly_avg_10k = total_teu / 12 / 10_000   # 만 TEU/월 평균

        for month in range(1, 13):
            dt = pd.Timestamp(year, month, 1)
            if dt > today:              # 미래 달 제외
                break
            monthly_records.append({
                'date':       dt,
                'throughput': round(monthly_avg_10k * _SEASONAL_NORM[month - 1], 2),
            })

    if not monthly_records:
        return None

    df = pd.DataFrame(monthly_records).sort_values('date').reset_index(drop=True)
    logger.info('BPA 물동량: %d개월 (계절분해, %d년~%d년)',
                len(df), start_year, df['date'].iloc[-1].year)
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. ECOS 한국은행 거시경제 (환율·유가·GDP 공식 데이터)
#    환경변수: ECOS_API_KEY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_ECOS_BASE = 'https://ecos.bok.or.kr/api/StatisticSearch'


def fetch_ecos_series(stat_code: str, item_code: str,
                      start_ym: str, end_ym: str,
                      cache_dir=None) -> pd.DataFrame | None:
    """
    한국은행 ECOS API → DataFrame(date, value).
    환경변수: ECOS_API_KEY
    """
    api_key = os.environ.get('ECOS_API_KEY', '')
    if not api_key:
        logger.info('ECOS_API_KEY 미설정')
        return None

    # 캐시 확인
    if cache_dir is not None:
        import pathlib
        cache_dir = pathlib.Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_fp = cache_dir / f'{stat_code}_{item_code}_{start_ym}_{end_ym}.csv'
        if cache_fp.exists():
            df = pd.read_csv(cache_fp, encoding='utf-8-sig')
            df['date'] = pd.to_datetime(df['date'])
            logger.info('ECOS 캐시 로드: %s', cache_fp.name)
            return df

    url = (f'{_ECOS_BASE}/{api_key}/json/kr/1/1000'
           f'/{stat_code}/M/{start_ym}/{end_ym}/{item_code}')
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        rows = resp.json().get('StatisticSearch', {}).get('row', [])
        if not rows:
            logger.debug('ECOS 응답 비어있음: %s/%s', stat_code, item_code)
            return None
        df = pd.DataFrame(rows)[['TIME', 'DATA_VALUE']].rename(
            columns={'TIME': 'date', 'DATA_VALUE': 'value'}
        )
        df['date']  = pd.to_datetime(df['date'].astype(str).str[:6], format='%Y%m')
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna().sort_values('date').reset_index(drop=True)
        logger.info('ECOS %s/%s: %d개월', stat_code, item_code, len(df))
        if cache_dir is not None:
            df.to_csv(cache_fp, index=False, encoding='utf-8-sig')
        return df
    except Exception as e:
        logger.warning('ECOS API 실패 (%s/%s): %s', stat_code, item_code, e)
        return None


def fetch_ecos_exchange_rate(start_ym: str = '202001', end_ym: str | None = None,
                             cache_dir=None) -> pd.DataFrame | None:
    """
    ECOS → 원/달러 환율 월평균.
    반환: DataFrame(date, exchange_rate)

    ECOS 통계코드 우선순위:
    - 731Y003 / 0000001 : 주요국통화의대원화환율 (USD, 월평균, 가장 안정적)
    - 731Y001 / 0000001 : 외환 통계 (달러/원)
    - 021Y151 / USD     : 원/달러 매매기준율
    """
    if end_ym is None:
        end_ym = datetime.today().strftime('%Y%m')

    # 여러 통계코드·항목코드 조합 시도 (ECOS 버전별 코드 차이 대응)
    candidates = [
        ('731Y003', '0000001'),   # 주요국통화의대원화환율 USD
        ('731Y001', '0000001'),   # 외환통계 달러/원
        ('021Y151', 'USD'),       # 원/달러 매매기준율
    ]
    for stat_code, item_code in candidates:
        df = fetch_ecos_series(stat_code, item_code, start_ym, end_ym, cache_dir)
        if df is not None and len(df) > 0:
            return df.rename(columns={'value': 'exchange_rate'})
    return None


def fetch_ecos_oil_price(start_ym: str = '202001', end_ym: str | None = None,
                         cache_dir=None) -> pd.DataFrame | None:
    """
    ECOS → 두바이유 월평균 (USD/배럴).
    반환: DataFrame(date, oil_price)

    ECOS 통계코드 우선순위:
    - 902Y020 / I61B  : 국제원자재가격 두바이유 (월평균)
    - 902Y020 / I61BCS: 두바이유 대안 항목코드
    - 902Y021 / I61B  : 유가 대안 통계
    """
    if end_ym is None:
        end_ym = datetime.today().strftime('%Y%m')

    candidates = [
        ('902Y020', 'I61B'),    # 두바이유 월평균 (기본)
        ('902Y020', 'I61BCS'),  # 두바이유 대안 코드
        ('902Y021', 'I61B'),    # 유가 대안 통계
    ]
    for stat_code, item_code in candidates:
        df = fetch_ecos_series(stat_code, item_code, start_ym, end_ym, cache_dir)
        if df is not None and len(df) > 0:
            return df.rename(columns={'value': 'oil_price'})
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. KCCI 한국형 컨테이너 운임지수 (공공데이터포털)
#    환경변수: DATA_GO_KR_KEY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_kcci_api(per_page: int = 500) -> pd.DataFrame | None:
    """
    공공데이터포털 KCCI API.
    반환: DataFrame(date, value)
    환경변수: DATA_GO_KR_KEY
    발급: https://www.data.go.kr/data/15131881/openapi.do 에서 활용신청
    """
    api_key = os.environ.get('DATA_GO_KR_KEY', '')
    if not api_key:
        logger.info('DATA_GO_KR_KEY 미설정 — KCCI API 건너뜀')
        return None

    url    = 'https://api.odcloud.kr/api/15131881/v1/uddi:5bf57a7e-2f36-4b77-85eb-5d0fb6247b0d'
    params = {'serviceKey': api_key, 'page': 1, 'perPage': per_page, 'returnType': 'JSON'}
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        rows = resp.json().get('data', [])
        if not rows:
            return None
        records: list[dict] = []
        for r in rows:
            date_val  = (r.get('발표일') or r.get('기준일') or r.get('date') or '')
            index_val = (r.get('KCCI') or r.get('종합지수') or r.get('value') or 0)
            try:
                records.append({
                    'date':  pd.to_datetime(str(date_val), errors='coerce'),
                    'value': float(str(index_val).replace(',', '')),
                })
            except (ValueError, TypeError):
                continue
        df = pd.DataFrame(records).dropna().sort_values('date').reset_index(drop=True)
        logger.info('KCCI: %d건', len(df))
        return df
    except Exception as e:
        logger.warning('KCCI API 실패: %s', e)
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. 통합 로더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_all_real_data(cache_dir=None, start: str = '2020-01-01') -> dict:
    """
    가능한 모든 실데이터를 수집해 dict로 반환.
    각 항목은 실패 시 None — 호출자가 시뮬로 폴백.
    """
    start_ym = start.replace('-', '')[:6]

    news     = fetch_maritime_news()
    # 환율: ECOS 우선, 실패 시 frankfurter
    fx_ecos  = fetch_ecos_exchange_rate(start_ym, cache_dir=cache_dir)
    fx       = fx_ecos if fx_ecos is not None else fetch_exchange_rate_monthly(start)
    # 유가: ECOS 우선 (두바이유), 실패 시 Brent stooq
    oil_ecos = fetch_ecos_oil_price(start_ym, cache_dir=cache_dir)
    oil      = oil_ecos if oil_ecos is not None else fetch_brent_oil_monthly(start)
    # 부산항 물동량
    bpa      = fetch_bpa_throughput(start_year=int(start[:4]))
    # KCCI
    kcci     = fetch_kcci_api()

    summary = {
        '해사뉴스':  f'{len(news)}건' if not news.empty else '실패',
        'USD/KRW':  f'{len(fx)}개월 ({"ECOS" if fx_ecos is not None else "frankfurter"})' if fx is not None else '실패',
        '유가':     f'{len(oil)}개월 ({"ECOS두바이유" if oil_ecos is not None else "Brent stooq"})' if oil is not None else '실패',
        '부산항':   f'{len(bpa)}개월 (계절분해)' if bpa is not None else 'API실패→CSV시도',
        'KCCI':     f'{len(kcci)}건' if kcci is not None else 'API키없음',
    }
    for k, v in summary.items():
        logger.info('  [실데이터] %s: %s', k, v)

    return {
        'news_df':       news,
        'exchange_rate': fx,
        'oil_price':     oil,
        'throughput':    bpa,
        'kcci':          kcci,
        '_summary':      summary,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. 데이터 상태 진단 (노트북 첫 실행 시 확인용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def print_data_status(cache_dir=None) -> None:
    """
    모든 데이터 소스의 현재 상태를 출력.
    노트북 실행 전에 실행해서 어느 데이터가 실데이터인지 확인.
    """
    import pathlib

    lines = [
        ('=' * 62),
        '  데이터 소스 현황',
        ('=' * 62),
    ]

    def _key(env: str) -> str:
        v = os.environ.get(env, '')
        return '✅ 설정됨' if v and not v.startswith('여기에') else '❌ 미설정'

    def _csv(path: str) -> str:
        p = pathlib.Path(path)
        if p.exists():
            size_kb = p.stat().st_size // 1024
            return f'✅ 있음 ({size_kb}KB)'
        return '❌ 없음'

    # API 키 상태
    lines += [
        '',
        '[API 키]',
        f'  ECOS (한국은행):       {_key("ECOS_API_KEY")}  → 환율·두바이유 공식',
        f'     ※ 통계코드 시도순: 731Y003/0000001 → 731Y001/0000001 → 021Y151/USD',
        f'     ※ 유가 시도순:    902Y020/I61B → 902Y020/I61BCS',
        f'     ※ ECOS 실패 시 → frankfurter.app(환율) / FRED(유가) 자동 대체',
        f'  BPA (부산항만공사):    {_key("BPA_API_KEY")}  → 컨테이너 물동량 (연도별)',
        f'     ※ BPA API 실패 시 → data/busan_throughput.csv 수동 다운로드 필요',
        f'  KCCI (공공데이터포털): {_key("DATA_GO_KR_KEY")}  → 운임지수',
        f'     ※ 발급: https://www.data.go.kr/data/15131881/openapi.do',
    ]

    # CSV 파일 상태
    data_dir = pathlib.Path('data') if pathlib.Path('data').exists() else pathlib.Path('../data')
    lines += [
        '',
        '[CSV 파일 (직접 다운로드)]',
        f'  KCCI:   {_csv(str(data_dir / "kcci.csv"))}',
        f'         다운로드: https://www.forwarder.kr/freight/index/kcci',
        f'  부산항: {_csv(str(data_dir / "busan_throughput.csv"))}',
        f'         다운로드: https://www.busanpa.com/kor/Contents.do?mCode=MN1003',
    ]

    # 자동 수집 (키 불필요)
    lines += [
        '',
        '[자동 수집 (키 불필요, 매일 08:30 자동 갱신)]',
        '  해사 뉴스 RSS: gCaptain / Splash247 / 한국해운신문',
        '  USD/KRW 환율:  frankfurter.app (일별 실시간)',
        '  Brent 유가:   Yahoo Finance BZ=F (일별 실시간)',
        '              → FRED MCOILBRENTEU (Yahoo 실패 시 폴백)',
        '              → EIA DEMO키 (최후 폴백)',
        '  갱신 명령:    python scripts/auto_update.py --mode daily',
        '',
        ('=' * 62),
    ]

    print('\n'.join(lines))
