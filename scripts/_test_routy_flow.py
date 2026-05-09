# -*- coding: utf-8 -*-
"""cell[24]~cell[28] 흐름 실제 실행 검증."""
import sys, os
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from datetime import datetime as _dt
import pandas as pd
from pathlib import Path

ROOT = Path('.').resolve()
(ROOT / 'data').mkdir(exist_ok=True)
(ROOT / 'routy_inputs').mkdir(exist_ok=True)

from src.odcy_recommender import recommend_storage, CargoType
from src.option_presenter import generate_four_options, format_option_table
from src.storage_routy_adapter import generate_storage_routy_json, generate_phase2_routy_json, save_storage_json

# Step 1 변수 (노트북 cell[6] 결과 시뮬)
SHIPPER_INPUT = {
    'company': '테스트화주(주)', 'cargo_type_str': '냉장화물',
    'cbm': 20.0, 'origin_address': '경기도 수원시 영통구',
    'route': '부산->로테르담', 'pickup_date': '2026-05-20',
    'deadline_days': 14, 'urgent': False,
}
CARGO_ENUM     = CargoType.REFRIGERATED
DEPARTURE_PORT = '부산항(북항)'
SHIPPER_REGION = '경기남부'

# Step 2 변수 (노트북 cell[11] 결과 시뮬)
today_mri    = 0.72
today_top_cat = '지정학분쟁'
MRI_THRESHOLD = 0.5

# ── cell[24]: ODCY 탐색 ──────────────────────────────────────
print('=== cell[24]: ODCY 탐색 ===')
kakao_key = os.getenv('KAKAO_REST_API_KEY', '')
mobi_key  = os.getenv('KAKAO_MOBILITY_KEY', '')

result = recommend_storage(
    port_name=DEPARTURE_PORT, cargo_type=CARGO_ENUM, top_n=3,
    kakao_rest_key=kakao_key or None, kakao_mobility_key=mobi_key or None,
)
mode = '카카오 실데이터' if not result['simulation_mode'] else '시뮬 DB'
top  = result['recommendations']['comprehensive'][0]
print(f'창고 탐색({mode}): {top["name"]} {top["distance_km"]}km')

_cargo_str = SHIPPER_INPUT['cargo_type_str']
SCENARIO = {
    'shipment_id':    f'SH-{_dt.now().strftime("%H%M%S")}',
    'port_name':      DEPARTURE_PORT,
    'cargo_type':     CARGO_ENUM,
    'cargo_type_str': _cargo_str,
    'company':        SHIPPER_INPUT['company'],
    'cbm':            SHIPPER_INPUT['cbm'],
    'region':         SHIPPER_REGION,
    'origin':         SHIPPER_INPUT['origin_address'],
    'pickup_date':    SHIPPER_INPUT['pickup_date'],
    'mri_now':        today_mri,
}
print(f'SCENARIO 키: {list(SCENARIO.keys())}')

# ── cell[25]: 4가지 옵션 ─────────────────────────────────────
print('\n=== cell[25]: 4가지 옵션 ===')
from src.scenario_engine import auto_classify_scenario
from src.config import SCENARIOS
_sid   = auto_classify_scenario(today_mri, today_top_cat)
_delay = SCENARIOS[_sid]['delay_days']
_freight = int(SCENARIO['cbm'] * 45)
_shipment_in = SCENARIO
_storage = result

options = generate_four_options(
    shipment=_shipment_in, storage_result=_storage,
    delay_days=_delay, freight_usd=_freight,
)
print(format_option_table(options))

# ── cell[28]: 루티 JSON ───────────────────────────────────────
print('\n=== cell[28]: 루티 JSON ===')
top_warehouse = result['recommendations']['comprehensive'][0]
_ctype  = SCENARIO.get('cargo_type_str', '일반화물')
_cold   = _ctype in ('냉장화물', '냉동화물', '2차전지')
_hazmat = _ctype in ('위험물', '2차전지')
_region = SCENARIO.get('region', '경기남부')

phase1 = generate_storage_routy_json(
    shipment_id          = SCENARIO['shipment_id'],
    company              = SCENARIO['company'],
    region               = _region,
    cargo_type           = SCENARIO['cargo_type_str'],
    cbm                  = SCENARIO['cbm'],
    cold_chain           = _cold,
    hazmat               = _hazmat,
    origin_address       = SCENARIO['origin'],
    original_port        = SCENARIO['port_name'],
    original_pickup_date = SCENARIO['pickup_date'],
    mri_current          = SCENARIO['mri_now'],
    delay_reason         = '해상 리스크 상승 (MRI 기반 HOLDBACK 결정)',
    recommended_warehouse = top_warehouse,
    phase2_ready_date    = '2026-05-25',
)
phase2 = generate_phase2_routy_json(
    phase1_json=phase1,
    cy_address='부산광역시 동구 초량동 부산항 1부두 CY',
    cy_closing_date='2026-05-23',
)
ROUTY_DIR = ROOT / 'routy_inputs'
for phase_name, data in [('Phase1', phase1), ('Phase2', phase2)]:
    fp = save_storage_json(data, ROUTY_DIR)
    assert fp.exists()
    print(f'{phase_name} 저장: {fp.name}')

print('\ncell[24]~[28] 전체 흐름 검증 완료')
