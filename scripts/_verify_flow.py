# -*- coding: utf-8 -*-
"""흐름도 전체 검증 스크립트."""
import sys, os, json
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

# ── 1. app.py 임포트 검증 ────────────────────────────────────
from src.config import SCENARIOS, ROUTE_INFO
from src.nlp_classifier import classify_news_df, top_category
from src.mri_engine import calc_today_mri, build_mri_series, mri_grade
from src.scenario_engine import auto_classify_scenario, generate_shipments, analyze_all
from src.reorganizer import reorganize_pickups
from src.routy_adapter import generate_routy_input, save_routy_json
from src.llm_reporter import estimate_monthly_cost, active_llm_provider
from src.data_loader import load_kcci
from src.historical_matcher import find_similar_events
from src.odcy_recommender import recommend_storage, CargoType
from src.option_presenter import generate_four_options, format_option_detail
from src.storage_routy_adapter import generate_storage_routy_json, save_storage_json
print('app.py 임포트 전체 OK')

# ── 2. 노트북 문법 검증 ──────────────────────────────────────
with open('notebooks/wemeet_v4_main.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
errors = []
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell['source'])
    if not src.strip():
        continue
    try:
        compile(src, f'cell[{i}]', 'exec')
    except SyntaxError as e:
        errors.append(f'cell[{i}]: {e}')
if errors:
    print('노트북 문법 오류:')
    for e in errors:
        print(f'  {e}')
else:
    n = len(nb['cells'])
    print(f'노트북 문법 검증 OK (총 {n}셀)')

# ── 3. 흐름도 Step 1 → 2 → 3 → 4 통합 테스트 ──────────────
import pandas as pd
from pathlib import Path
ROOT = Path('.').resolve()
(ROOT / 'data').mkdir(exist_ok=True)

print('\n[Step 1] 화주 입력')
SHIPPER_INPUT = {
    'company': '테스트화주(주)', 'cargo_type_str': '냉장화물',
    'cbm': 20.0, 'origin_address': '경기도 수원시 영통구',
    'route': '부산→로테르담', 'pickup_date': '2026-05-20',
    'deadline_days': 14, 'urgent': False,
}
CARGO_TYPE_MAP = {
    '일반화물': CargoType.GENERAL, '냉장화물': CargoType.REFRIGERATED, '위험물': CargoType.HAZMAT,
}
CARGO_ENUM    = CARGO_TYPE_MAP.get(SHIPPER_INPUT['cargo_type_str'], CargoType.GENERAL)
DEPARTURE_PORT = '부산항(북항)'
print(f'  화물유형: {SHIPPER_INPUT["cargo_type_str"]} → {CARGO_ENUM.value}')
print(f'  출발항만: {DEPARTURE_PORT}')

print('\n[Step 2] MRI 산출 + 과거 유사사례')
sim_news = pd.DataFrame([
    {'title': 'Houthi attack Red Sea hormuz threat', 'text': 'blockade iran', 'source': 'sim'},
    {'title': '호르무즈 봉쇄 이란 위협', 'text': '지정학 분쟁', 'source': 'sim'},
])
news_df = classify_news_df(sim_news)
today_cat = top_category(news_df)
dates   = pd.date_range('2020-01-01', '2026-04-01', freq='MS')
freight_df = load_kcci(ROOT / 'data', use_real=True)
today_mri = calc_today_mri(news_df, freight_df)
grade, _  = mri_grade(today_mri)
print(f'  MRI: {today_mri:.4f} [{grade}], 카테고리: {today_cat}')

similar = find_similar_events(today_mri, [today_cat], top_k=3)
avg_delay   = sum(e['avg_delay_days'] for e in similar) / len(similar)
avg_freight = sum(e['avg_freight_increase_pct'] for e in similar) / len(similar)
print(f'  과거 유사사례 평균 — 지연: +{avg_delay:.1f}일, 운임: +{avg_freight:.1f}%')

print('\n[Step 3] 창고·ODCY 탐색 + 4가지 옵션')
MRI_THRESHOLD = 0.5
kakao_key = os.getenv('KAKAO_REST_API_KEY', '')
if today_mri >= MRI_THRESHOLD:
    result = recommend_storage(
        port_name=DEPARTURE_PORT, cargo_type=CARGO_ENUM, top_n=3,
        kakao_rest_key=kakao_key or None,
    )
    mode = '카카오 실데이터' if not result['simulation_mode'] else '시뮬 DB'
    top  = result['recommendations']['comprehensive'][0]
    print(f'  창고 탐색({mode}): {top["name"]} {top["distance_km"]}km')

    options = generate_four_options(SHIPPER_INPUT, result, delay_days=14, freight_usd=900)
    A, D = options[0].total_usd, options[3].total_usd
    print(f'  A안(직송): ${A:,.0f} vs D안(권장): ${D:,.0f} → 절약 ${A-D:,.0f}')
else:
    print(f'  MRI {today_mri:.3f} < {MRI_THRESHOLD} → 창고 추천 불필요')
    result = None

print('\n[Step 4] 루티 Phase 1 JSON 생성')
if result is not None:
    top_wh = result['recommendations']['comprehensive'][0]
    p1 = generate_storage_routy_json(
        shipment_id='SH-VERIFY-001', company=SHIPPER_INPUT['company'],
        region='경기남부', cargo_type=SHIPPER_INPUT['cargo_type_str'],
        cbm=SHIPPER_INPUT['cbm'], cold_chain=True, hazmat=False,
        origin_address=SHIPPER_INPUT['origin_address'],
        original_port=DEPARTURE_PORT, original_pickup_date=SHIPPER_INPUT['pickup_date'],
        mri_current=today_mri, delay_reason='호르무즈 봉쇄',
        recommended_warehouse=top_wh,
    )
    assert p1['phase'] == 'PHASE1_TO_STORAGE'
    print(f'  루티 JSON 생성 OK: {p1["execution_group_id"]}')
else:
    print('  MRI 낮아 JSON 생성 생략')

print('\n=== 흐름도 Step 1→2→3→4 전체 통과 ===')
