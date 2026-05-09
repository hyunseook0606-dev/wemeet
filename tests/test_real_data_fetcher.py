"""tests/test_real_data_fetcher.py — 실데이터 수집 모듈 단위 테스트

네트워크 의존 테스트는 @pytest.mark.network 로 분류.
기본 실행 시 건너뜀: pytest tests/ -m "not network"
"""
import os
import pytest
import pandas as pd

from src.real_data_fetcher import (
    _parse_bpa_rows,
    _SEASONAL_NORM,
    _BUSAN_SEASONAL,
)


# ── 계절 가중치 검증 ───────────────────────────────────────────────────────────

def test_seasonal_norm_sums_to_12():
    """월별 계절 가중치의 합이 12여야 함 (연평균 × 12개월 = 연간 합계)."""
    assert abs(sum(_SEASONAL_NORM) - 12.0) < 1e-6


def test_seasonal_norm_length():
    assert len(_SEASONAL_NORM) == 12


def test_seasonal_feb_min():
    """2월(인덱스 1)이 최저 계절 가중치여야 함 (설 연휴)."""
    assert _SEASONAL_NORM[1] == min(_SEASONAL_NORM)


def test_seasonal_dec_max():
    """12월(인덱스 11)이 최고 계절 가중치여야 함 (연말 성수기)."""
    assert _SEASONAL_NORM[11] == max(_SEASONAL_NORM)


# ── BPA 행 파싱 ───────────────────────────────────────────────────────────────

def test_parse_bpa_rows_teu_unit():
    """TEU 단위 자동 변환: 23,000,000 TEU → 약 230만 TEU → 230 만 TEU."""
    rows = [{'YEAR': '2023', 'TOTAL_TEU': '23000000'}]
    result = _parse_bpa_rows(rows)
    assert len(result) == 1
    assert result[0]['year'] == 2023
    assert abs(result[0]['teu_10k'] - 2300.0) < 1


def test_parse_bpa_rows_already_manteu():
    """이미 만 TEU 단위(약 230 범위)이면 그대로."""
    rows = [{'YEAR': '2024', 'TOTAL_TEU': '230'}]
    result = _parse_bpa_rows(rows)
    assert result[0]['teu_10k'] == pytest.approx(23.0, abs=1)


def test_parse_bpa_rows_korean_keys():
    """한글 컬럼명 지원."""
    rows = [{'연도': '2022', '합계': '20000000'}]
    result = _parse_bpa_rows(rows)
    assert len(result) == 1
    assert result[0]['year'] == 2022


def test_parse_bpa_rows_bad_data():
    """파싱 불가 행은 조용히 건너뜀."""
    rows = [
        {'YEAR': 'N/A', 'TOTAL_TEU': '23000000'},
        {'YEAR': '2023', 'TOTAL_TEU': 'invalid'},
        {'YEAR': '2024', 'TOTAL_TEU': '22000000'},
    ]
    result = _parse_bpa_rows(rows)
    assert len(result) == 1
    assert result[0]['year'] == 2024


def test_parse_bpa_rows_sorted():
    """연도 오름차순 정렬."""
    rows = [
        {'YEAR': '2024', 'TOTAL_TEU': '22000000'},
        {'YEAR': '2022', 'TOTAL_TEU': '20000000'},
        {'YEAR': '2023', 'TOTAL_TEU': '21000000'},
    ]
    result = _parse_bpa_rows(rows)
    years = [r['year'] for r in result]
    assert years == sorted(years)


# ── 네트워크 의존 테스트 (기본 실행 시 건너뜀) ────────────────────────────────

@pytest.mark.network
def test_fetch_exchange_rate_monthly_real():
    """frankfurter.app 환율 실제 수집."""
    from src.real_data_fetcher import fetch_exchange_rate_monthly
    df = fetch_exchange_rate_monthly(start='2024-01-01')
    assert df is not None
    assert len(df) >= 6
    assert 'exchange_rate' in df.columns
    assert df['exchange_rate'].mean() > 1000  # 원/달러는 1000 이상


@pytest.mark.network
def test_fetch_brent_oil_monthly_real():
    """stooq.com Brent 유가 실제 수집."""
    from src.real_data_fetcher import fetch_brent_oil_monthly
    df = fetch_brent_oil_monthly(start='2024-01-01')
    assert df is not None
    assert len(df) >= 6
    assert 'oil_price' in df.columns
    assert 50 < df['oil_price'].mean() < 200  # 배럴당 합리적인 범위


@pytest.mark.network
def test_fetch_maritime_news_real():
    """RSS 뉴스 수집 (feedparser 필요)."""
    try:
        import feedparser
    except ImportError:
        pytest.skip('feedparser 미설치')
    from src.real_data_fetcher import fetch_maritime_news
    df = fetch_maritime_news(max_per_source=5, days_back=30)
    # 최소 1개 소스라도 성공하면 OK
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        assert 'title' in df.columns
        assert 'source' in df.columns


@pytest.mark.network
def test_fetch_ecos_exchange_rate_real():
    """ECOS API 환율 수집 (키 있을 때만)."""
    if not os.environ.get('ECOS_API_KEY'):
        pytest.skip('ECOS_API_KEY 미설정')
    from src.real_data_fetcher import fetch_ecos_exchange_rate
    df = fetch_ecos_exchange_rate('202401')
    assert df is not None
    assert 'exchange_rate' in df.columns
    assert df['exchange_rate'].mean() > 1000


@pytest.mark.network
def test_fetch_ecos_oil_price_real():
    """ECOS API 두바이유 수집 (키 있을 때만)."""
    if not os.environ.get('ECOS_API_KEY'):
        pytest.skip('ECOS_API_KEY 미설정')
    from src.real_data_fetcher import fetch_ecos_oil_price
    df = fetch_ecos_oil_price('202401')
    assert df is not None
    assert 'oil_price' in df.columns
    assert 50 < df['oil_price'].mean() < 200
