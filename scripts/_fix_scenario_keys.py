# -*- coding: utf-8 -*-
"""SCENARIO dict 키 누락 + 중복 블록 수정."""
import json
from pathlib import Path

NB = Path(__file__).parent.parent / 'notebooks' / 'wemeet_v4_main.ipynb'

with open(NB, encoding='utf-8') as f:
    nb = json.load(f)
cells = nb['cells']


def find_cell(keyword):
    for i, c in enumerate(cells):
        if keyword in ''.join(c['source']):
            return i
    return None


# ─────────────────────────────────────────────────────────────
# FIX 1: cell[24] SCENARIO dict에 shipment_id / region 추가
# ─────────────────────────────────────────────────────────────
idx_odcy = find_cell('recommend_storage')
if idx_odcy is not None:
    src = ''.join(cells[idx_odcy]['source'])

    old_scenario = (
        '    # 이후 셀에서 사용할 SCENARIO dict 자동 구성\n'
        '    SCENARIO = {\n'
        '        "port_name":   _port,\n'
        '        "cargo_type":  _cargo_enum,\n'
        '        "company":     _company,\n'
        '        "cbm":         _cbm,\n'
        '        "origin":      _origin,\n'
        '        "pickup_date": _pickup,\n'
        '        "mri_now":     _mri_now,\n'
        '        "cargo_type_str": _cargo_str,\n'
        '    }\n'
    )
    new_scenario = (
        '    # 이후 셀에서 사용할 SCENARIO dict 자동 구성\n'
        '    from datetime import datetime as _dt\n'
        '    try:\n'
        '        _region = SHIPPER_REGION\n'
        '    except NameError:\n'
        '        _region = "경기남부"\n'
        '    SCENARIO = {\n'
        '        "shipment_id":    f"SH-{_dt.now().strftime(\'%H%M%S\')}",\n'
        '        "port_name":      _port,\n'
        '        "cargo_type":     _cargo_enum,\n'
        '        "cargo_type_str": _cargo_str,\n'
        '        "company":        _company,\n'
        '        "cbm":            _cbm,\n'
        '        "region":         _region,\n'
        '        "origin":         _origin,\n'
        '        "pickup_date":    _pickup,\n'
        '        "mri_now":        _mri_now,\n'
        '    }\n'
    )
    if old_scenario in src:
        src = src.replace(old_scenario, new_scenario)
        cells[idx_odcy]['source'] = [src]
        cells[idx_odcy]['outputs'] = []
        cells[idx_odcy]['execution_count'] = None
        print(f'FIX1: SCENARIO dict 수정 (cell[{idx_odcy}])')
    else:
        print(f'FIX1: 패턴 미발견 — 직접 확인 필요 (cell[{idx_odcy}])')


# ─────────────────────────────────────────────────────────────
# FIX 2: cell[25] 중복 _storage 블록 제거
# ─────────────────────────────────────────────────────────────
idx_opt = find_cell('option_presenter')
if idx_opt is not None:
    src = ''.join(cells[idx_opt]['source'])
    dup_block = (
        '\ntry:\n'
        '    _storage = result\n'
        'except NameError:\n'
        '    from src.odcy_recommender import recommend_storage, CargoType\n'
        "    _storage = recommend_storage('부산항(북항)', CargoType.GENERAL, top_n=3)\n"
    )
    count = src.count(dup_block)
    if count >= 2:
        # 두 번째 중복 블록만 제거
        idx_first = src.index(dup_block)
        idx_second = src.index(dup_block, idx_first + 1)
        src = src[:idx_second] + src[idx_second + len(dup_block):]
        cells[idx_opt]['source'] = [src]
        cells[idx_opt]['outputs'] = []
        cells[idx_opt]['execution_count'] = None
        print(f'FIX2: 중복 _storage 블록 제거 (cell[{idx_opt}])')
    else:
        print(f'FIX2: 중복 없음 (cell[{idx_opt}])')


# ─────────────────────────────────────────────────────────────
# FIX 3: cell[28] 루티 JSON — CARGO_REQUIREMENTS 의존성 제거
#         region 하드코딩 제거, shipment_id 사용
# ─────────────────────────────────────────────────────────────
idx_routy = find_cell('generate_storage_routy_json')
if idx_routy is not None:
    NEW_ROUTY_SRC = [
        'from src.storage_routy_adapter import (\n',
        '    generate_storage_routy_json, generate_phase2_routy_json, save_storage_json\n',
        ')\n',
        'from pathlib import Path\n',
        'import json\n',
        '\n',
        'ROUTY_DIR = ROOT / "routy_inputs"\n',
        'ROUTY_DIR.mkdir(exist_ok=True)\n',
        '\n',
        'if result is None:\n',
        '    print("MRI 임계값 미만 — 루티 JSON 생성 생략 (평상시 운영)")\n',
        'else:\n',
        '    top_warehouse = result["recommendations"]["comprehensive"][0]\n',
        '\n',
        '    # 화물 유형에 따른 cold_chain / hazmat 자동 결정\n',
        '    _ctype   = SCENARIO.get("cargo_type_str", "일반화물")\n',
        '    _cold    = _ctype in ("냉장화물", "냉동화물", "2차전지")\n',
        '    _hazmat  = _ctype in ("위험물", "2차전지")\n',
        '    _region  = SCENARIO.get("region", "경기남부")\n',
        '\n',
        '    # ── Phase 1: 출발지 → 창고 ──────────────────────────────\n',
        '    phase1 = generate_storage_routy_json(\n',
        '        shipment_id          = SCENARIO["shipment_id"],\n',
        '        company              = SCENARIO["company"],\n',
        '        region               = _region,\n',
        '        cargo_type           = SCENARIO["cargo_type_str"],\n',
        '        cbm                  = SCENARIO["cbm"],\n',
        '        cold_chain           = _cold,\n',
        '        hazmat               = _hazmat,\n',
        '        origin_address       = SCENARIO["origin"],\n',
        '        original_port        = SCENARIO["port_name"],\n',
        '        original_pickup_date = SCENARIO["pickup_date"],\n',
        '        mri_current          = SCENARIO["mri_now"],\n',
        '        delay_reason         = "해상 리스크 상승 (MRI 기반 HOLDBACK 결정)",\n',
        '        recommended_warehouse = top_warehouse,\n',
        '        phase2_ready_date    = "2026-05-25",\n',
        '    )\n',
        '\n',
        '    # ── Phase 2: 창고 → CY ──────────────────────────────────\n',
        '    phase2 = generate_phase2_routy_json(\n',
        '        phase1_json     = phase1,\n',
        '        cy_address      = "부산광역시 동구 초량동 부산항 1부두 CY",\n',
        '        cy_closing_date = "2026-05-23",\n',
        '    )\n',
        '\n',
        '    # ── 출력 & 저장 ─────────────────────────────────────────\n',
        '    SEP = "=" * 60\n',
        '    for phase_name, data in [("Phase 1 (출발지->창고)", phase1), ("Phase 2 (창고->CY)", phase2)]:\n',
        '        print()\n',
        '        print(SEP)\n',
        '        print("루티 JSON --", phase_name)\n',
        '        print(SEP)\n',
        '        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))\n',
        '        fp = save_storage_json(data, ROUTY_DIR)\n',
        '        print("저장 완료:", fp.name)\n',
    ]
    cells[idx_routy]['source'] = NEW_ROUTY_SRC
    cells[idx_routy]['outputs'] = []
    cells[idx_routy]['execution_count'] = None
    print(f'FIX3: 루티 JSON 셀 재작성 (cell[{idx_routy}])')


# ─────────────────────────────────────────────────────────────
# 저장 + 문법 검증
# ─────────────────────────────────────────────────────────────
with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

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
    print('\n문법 오류:')
    for e in errors:
        print(f'  {e}')
else:
    print(f'\n문법 검증 OK (총 {len(nb["cells"])}셀)')
print('저장 완료')
