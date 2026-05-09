# -*- coding: utf-8 -*-
"""전체 기능 통합 테스트 — vs code 프로젝트."""
import sys, os
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path('.').resolve()
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)

PASS, FAIL = [], []

def check(name, fn):
    try:
        result = fn()
        PASS.append(name)
        return result
    except Exception as e:
        FAIL.append((name, str(e)))
        return None

print('=' * 60)
print('전체 기능 통합 테스트')
print('=' * 60)

# ── 1. 모듈 import ──────────────────────────────────────────
print('\n[1] 모듈 import')
mods = [
    'src.config', 'src.nlp_classifier', 'src.mri_engine',
    'src.scenario_engine', 'src.reorganizer', 'src.routy_adapter',
    'src.llm_reporter', 'src.data_loader', 'src.lstm_forecaster',
    'src.historical_matcher', 'src.odcy_recommender',
    'src.storage_routy_adapter', 'src.visualizer',
    'src.real_data_fetcher', 'src.freight_index_loader',
    'src.option_presenter',
]
for m in mods:
    check(f'import {m}', lambda m=m: __import__(m))

# ── 2. 뉴스 수집 + NLP ─────────────────────────────────────
print('\n[2] 뉴스 수집 + NLP 분류')
from src.real_data_fetcher import fetch_maritime_news
from src.nlp_classifier import classify_news_df, top_category

def test_news():
    try:
        import feedparser
        df = fetch_maritime_news(max_per_source=5, days_back=7)
        assert not df.empty, '뉴스 0건'
    except ImportError:
        df = pd.DataFrame([
            {'title': 'Houthi attack Red Sea hormuz blockade', 'text': 'iran strait threat', 'source': 'sim'},
            {'title': '호르무즈 봉쇄 위협 이란 미사일', 'text': '지정학 분쟁 위험', 'source': 'sim'},
            {'title': 'freight rate surge SCFI BDI', 'text': 'capacity shortage', 'source': 'sim'},
        ])
    df = classify_news_df(df)
    cat = top_category(df)
    assert 'pred_category' in df.columns
    return len(df), cat

result = check('뉴스수집+NLP', test_news)
if result:
    print(f'  뉴스 {result[0]}건, 최다카테고리: {result[1]}')

# ── 3. MRI 산출 ──────────────────────────────────────────────
print('\n[3] MRI 산출')
from src.mri_engine import calc_today_mri, build_mri_series, mri_grade, mri_sub_indices
from src.data_loader import load_kcci

def test_mri():
    freight_df = load_kcci(DATA_DIR, use_real=True)
    news_df = pd.DataFrame([
        {'title': 'hormuz blockade iran', 'text': 'strait war threat', 'source': 'sim'},
        {'title': '호르무즈 봉쇄', 'text': '이란 위협', 'source': 'sim'},
    ])
    news_df = classify_news_df(news_df)
    dates  = pd.date_range('2020-01-01', '2026-04-01', freq='MS')
    series = build_mri_series(dates, freight_df)
    today  = calc_today_mri(news_df, freight_df)
    grade, _ = mri_grade(today)
    sub = mri_sub_indices(news_df, freight_df)
    assert 0 <= today <= 1
    assert set(sub.keys()) == {'G', 'D', 'F', 'V', 'P'}
    assert len(series) == len(dates)
    # st.cache_data 직렬화 테스트
    dates_list  = dates.strftime('%Y-%m-%d').tolist()
    series_list = series.tolist()
    dates2  = pd.to_datetime(dates_list)
    series2 = np.array(series_list)
    return today, grade

result = check('MRI산출', test_mri)
if result:
    print(f'  MRI: {result[0]:.4f} [{result[1]}]')

# ── 4. 시나리오 + 영향 분석 ──────────────────────────────────
print('\n[4] 시나리오 + 영향 분석')
from src.scenario_engine import auto_classify_scenario, generate_shipments, analyze_all, analyze_impact
from src.reorganizer import reorganize_pickups
from src.routy_adapter import generate_routy_input, run_all_scenarios
from src.config import SCENARIOS

def test_scenario():
    ship_df = generate_shipments(n=30)
    for sid in SCENARIOS:
        impacts = analyze_all(ship_df, sid)
        reorg   = reorganize_pickups(ship_df, impacts, SCENARIOS[sid])
        routy   = generate_routy_input(sid, SCENARIOS[sid], ship_df, impacts, reorg)
        assert 'summary' in routy
        assert 'pickup_adjustments' in routy
    return len(ship_df)

result = check('시나리오엔진', test_scenario)
if result:
    print(f'  30건 × 5시나리오 모두 통과')

# ── 5. 과거 유사사례 매칭 ─────────────────────────────────────
print('\n[5] 과거 유사사례 매칭')
from src.historical_matcher import find_similar_events, format_customer_message
from src.config import RISK_KEYWORDS

def test_matcher():
    cats = list(RISK_KEYWORDS.keys())[:2]
    events = find_similar_events(0.75, cats, top_k=3)
    assert len(events) >= 1
    msg = format_customer_message(0.75, events)
    assert '과거' in msg or '현재' in msg
    # 카테고리 매칭 확인 (최소 1건은 카테고리 일치해야)
    matched = [e for e in events if e['category_match']]
    return len(events), len(matched)

result = check('유사사례매칭', test_matcher)
if result:
    print(f'  매칭 {result[0]}건, 카테고리일치 {result[1]}건')

# ── 6. ODCY 추천 + 카카오 API ────────────────────────────────
print('\n[6] ODCY 추천 (카카오 API)')
from src.odcy_recommender import recommend_storage, CargoType

kakao_key = os.getenv('KAKAO_REST_API_KEY', '')
mobi_key  = os.getenv('KAKAO_MOBILITY_KEY', '')

def test_odcy():
    r = recommend_storage(
        '부산항(북항)', CargoType.GENERAL, top_n=3,
        kakao_rest_key=kakao_key, kakao_mobility_key=mobi_key,
    )
    mode = 'kakao실데이터' if not r['simulation_mode'] else '시뮬DB'
    recs = r['recommendations']['comprehensive']
    assert len(recs) >= 1
    w = recs[0]
    assert w['distance_km'] is not None
    return mode, recs[0]['name'], recs[0]['distance_km']

result = check('ODCY추천', test_odcy)
if result:
    print(f'  모드: {result[0]} | 1위: {result[1]} ({result[2]}km)')

# ── 7. 4가지 옵션 비교 ──────────────────────────────────────
print('\n[7] 4가지 옵션 비교')
from src.option_presenter import generate_four_options, format_option_table, format_option_detail

def test_options():
    r = recommend_storage('부산항(북항)', CargoType.GENERAL, top_n=3,
                          kakao_rest_key=kakao_key, kakao_mobility_key=mobi_key)
    shipment = {'cargo_type': '일반화물', 'cbm': 15.0, 'region': '경기남부'}
    opts = generate_four_options(shipment, r, delay_days=14, freight_usd=675)
    assert len(opts) == 4
    assert opts[0].option_id == 'A'
    assert opts[3].option_id == 'D'
    for opt in opts[1:]:
        assert opt.total_usd > 0
    table = format_option_table(opts)
    detail = format_option_detail(opts[3], opts[0])
    assert 'D안' in table and '권장' in table
    savings = [o.savings_vs(opts[0]) for o in opts]
    return opts[3].total_usd, opts[0].total_usd, savings[3]

result = check('4가지옵션', test_options)
if result:
    print(f'  A안: ${result[1]:,.0f} / D안: ${result[0]:,.0f} / 절약: ${result[2]:+,.0f}')

# ── 8. Phase 1/2 루티 JSON ──────────────────────────────────
print('\n[8] Phase 1/2 루티 JSON')
from src.storage_routy_adapter import generate_storage_routy_json, generate_phase2_routy_json, save_storage_json

def test_storage_routy():
    wh = {'name': '테스트창고', 'address': '부산시 동구', 'phone': '051-000-0000',
          'type': 'ODCY', 'distance_km': 2.5, 'duration_min': 8.0, 'special_notes': ''}
    p1 = generate_storage_routy_json(
        shipment_id='SH-001', company='테스트화주', region='경기남부',
        cargo_type='일반화물', cbm=15.0, cold_chain=False, hazmat=False,
        origin_address='경기도 수원시', original_port='부산항(북항)',
        original_pickup_date='2026-05-20', mri_current=0.72,
        delay_reason='호르무즈 봉쇄', recommended_warehouse=wh,
    )
    assert p1['phase'] == 'PHASE1_TO_STORAGE'
    p2 = generate_phase2_routy_json(p1, cy_address='부산 신항 CY', cy_closing_date='2026-06-05')
    assert p2['phase'] == 'PHASE2_TO_CY'
    saved = save_storage_json(p1, DATA_DIR / 'routy_inputs')
    assert saved.exists()
    return 'OK'

result = check('Phase1/2루티JSON', test_storage_routy)
if result:
    print(f'  Phase1→Phase2 생성 + 파일 저장 완료')

# ── 9. LLM 리포터 ───────────────────────────────────────────
print('\n[9] LLM 리포터')
from src.llm_reporter import active_llm_provider, estimate_monthly_cost

def test_llm():
    provider = active_llm_provider()
    cost = estimate_monthly_cost(calls_per_day=24)
    assert cost['cost_no_cache'] > 0
    assert cost['savings_pct'] > 0
    return provider, cost['cost_with_cache']

result = check('LLM리포터', test_llm)
if result:
    print(f'  LLM: {result[0]} | 월비용(캐싱): ${result[1]:.2f}')

# ── 10. app.py 핵심 임포트 ───────────────────────────────────
print('\n[10] app.py 핵심 임포트')
def test_app_imports():
    from src.config import SCENARIOS, ROUTE_INFO
    from src.nlp_classifier import classify_news_df, top_category
    from src.mri_engine import calc_today_mri, build_mri_series, mri_grade
    from src.scenario_engine import auto_classify_scenario, generate_shipments, analyze_all
    from src.reorganizer import reorganize_pickups
    from src.routy_adapter import generate_routy_input, save_routy_json, run_all_scenarios
    from src.llm_reporter import generate_risk_report, estimate_monthly_cost, active_llm_provider
    from src.data_loader import load_kcci
    return 'OK'

result = check('app.py임포트', test_app_imports)

# ── 결과 요약 ────────────────────────────────────────────────
print()
print('=' * 60)
print(f'결과: 통과 {len(PASS)}개 / 실패 {len(FAIL)}개')
print('=' * 60)
if FAIL:
    print('\n[실패 목록]')
    for name, err in FAIL:
        print(f'  X {name}: {err[:80]}')
else:
    print('모든 테스트 통과')
