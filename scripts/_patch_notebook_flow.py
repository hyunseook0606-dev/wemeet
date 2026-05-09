# -*- coding: utf-8 -*-
"""
흐름도 기반 노트북 전면 패치
1. 화주 입력 셀 삽입 (Step 1)
2. cell[19] 변수명 불일치 수정 (mri_score → today_mri)
3. cell[23] 하드코딩 제거 + MRI 조건 추가 + 화물유형 자동 변환
4. cell[24] 실제 지연일수 연동
5. cell[27] 루티 JSON 화주 입력 연동
"""
import json
from pathlib import Path

NB = Path(__file__).parent.parent / 'notebooks' / 'wemeet_v4_main.ipynb'

with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']

# ─────────────────────────────────────────────────────────────
# STEP 1. 화주 데이터 입력 셀 삽입 (cell[05] markdown 다음)
# ─────────────────────────────────────────────────────────────

SHIPPER_INPUT_SRC = [
    '# ══════════════════════════════════════════════════════\n',
    '# Step 1. 화주 데이터 입력\n',
    '# 아래 값을 수정하면 이후 전체 분석이 자동으로 반영됩니다.\n',
    '# 실제 서비스: 웹폼/앱 입력값이 이 변수들에 자동 주입됩니다.\n',
    '# ══════════════════════════════════════════════════════\n',
    'from src.odcy_recommender import CargoType\n',
    'import os\n',
    '\n',
    '# ── 화주 입력 정보 ──────────────────────────────────────\n',
    'SHIPPER_INPUT = {\n',
    '    "company":        "테스트화주(주)",\n',
    '    "cargo_type_str": "일반화물",        # 일반화물 / 냉장화물 / 위험물\n',
    '    "cbm":            15.0,              # 화물 용량 (CBM)\n',
    '    "origin_address": "경기도 수원시 영통구",\n',
    '    "route":          "부산\\u2192로테르담",\n',
    '    "pickup_date":    "2026-05-20",\n',
    '    "deadline_days":  14,\n',
    '    "urgent":         False,\n',
    '}\n',
    '\n',
    '# 항로 → 출발 항만 자동 결정\n',
    'ROUTE_TO_PORT = {\n',
    '    "부산\\u2192로테르담": "부산항(북항)",\n',
    '    "부산\\u2192LA":       "부산항(북항)",\n',
    '    "부산\\u2192상하이":   "부산항(북항)",\n',
    '    "부산\\u2192싱가포르": "부산 신항",\n',
    '    "부산\\u2192도쿄":     "부산항(북항)",\n',
    '}\n',
    'DEPARTURE_PORT = ROUTE_TO_PORT.get(SHIPPER_INPUT["route"], "부산항(북항)")\n',
    '\n',
    '# 화물유형 문자열 → CargoType enum 자동 변환\n',
    'CARGO_TYPE_MAP = {\n',
    '    "일반화물":  CargoType.GENERAL,\n',
    '    "냉장화물":  CargoType.REFRIGERATED,\n',
    '    "위험물":    CargoType.HAZMAT,\n',
    '    "자동차부품": CargoType.AUTO_PARTS,\n',
    '    "2차전지":   CargoType.BATTERY,\n',
    '    "의류/섬유": CargoType.APPAREL,\n',
    '    "전자제품":  CargoType.ELECTRONICS,\n',
    '}\n',
    'CARGO_ENUM = CARGO_TYPE_MAP.get(SHIPPER_INPUT["cargo_type_str"], CargoType.GENERAL)\n',
    '\n',
    '# 출발지 주소 → 권역 자동 결정 (실제 서비스: 카카오 지오코딩 사용)\n',
    'def _addr_to_region(addr: str) -> str:\n',
    '    if any(k in addr for k in ["수원", "화성", "평택", "안산", "용인", "안양"]):\n',
    '        return "경기남부"\n',
    '    if any(k in addr for k in ["서울", "경기", "인천", "의정부", "고양", "파주"]):\n',
    '        return "경기북부"\n',
    '    if any(k in addr for k in ["충남", "충북", "대전", "세종", "천안", "아산"]):\n',
    '        return "충청"\n',
    '    if any(k in addr for k in ["부산", "울산", "경남", "창원", "진주"]):\n',
    '        return "경상남부"\n',
    '    if any(k in addr for k in ["대구", "경북", "포항", "구미", "안동"]):\n',
    '        return "경상북도"\n',
    '    return "경기남부"\n',
    '\n',
    'SHIPPER_REGION = _addr_to_region(SHIPPER_INPUT["origin_address"])\n',
    '\n',
    'print("=" * 55)\n',
    'print("Step 1. 화주 입력 정보")\n',
    'print("=" * 55)\n',
    'print(f"  회사명    : {SHIPPER_INPUT[\'company\']}")\n',
    'print(f"  화물 유형 : {SHIPPER_INPUT[\'cargo_type_str\']} → {CARGO_ENUM.value}")\n',
    'print(f"  화물 용량 : {SHIPPER_INPUT[\'cbm\']} CBM")\n',
    'print(f"  출발지    : {SHIPPER_INPUT[\'origin_address\']}")\n',
    'print(f"  권역(자동): {SHIPPER_REGION}")\n',
    'print(f"  희망 항로 : {SHIPPER_INPUT[\'route\']}")\n',
    'print(f"  출발 항만 : {DEPARTURE_PORT}")\n',
    'print(f"  집화 예정 : {SHIPPER_INPUT[\'pickup_date\']}")\n',
    'print(f"  납기 여유 : {SHIPPER_INPUT[\'deadline_days\']}일")\n',
    'print("=" * 55)\n',
]

# cell[05]가 markdown '---' 인지 확인 후 바로 뒤에 삽입
insert_idx = 6   # cell[05] 다음
# 이미 삽입됐는지 확인
already = any('SHIPPER_INPUT' in ''.join(c['source']) for c in cells)
if already:
    # 기존 셀 업데이트
    for i, c in enumerate(cells):
        if 'SHIPPER_INPUT' in ''.join(c['source']):
            cells[i]['source'] = SHIPPER_INPUT_SRC
            cells[i]['outputs'] = []
            cells[i]['execution_count'] = None
            insert_idx = None
            print(f'SHIPPER_INPUT 셀 업데이트 (cell[{i}])')
            break
else:
    new_cell = {
        'cell_type': 'code',
        'execution_count': None,
        'metadata': {},
        'outputs': [],
        'source': SHIPPER_INPUT_SRC,
    }
    cells.insert(insert_idx, new_cell)
    print(f'SHIPPER_INPUT 셀 삽입 (cell[{insert_idx}])')

# 삽입 후 인덱스 재계산
def find_cell(keyword):
    for i, c in enumerate(cells):
        if keyword in ''.join(c['source']):
            return i
    return None

# ─────────────────────────────────────────────────────────────
# STEP 2. cell[19] 변수명 불일치 수정 (historical_matcher)
# ─────────────────────────────────────────────────────────────

idx_hist = find_cell('find_similar_events')
if idx_hist is not None:
    src = ''.join(cells[idx_hist]['source'])
    # mri_score → today_mri, detected_categories → [today_top_cat]
    new_src = src
    new_src = new_src.replace(
        "try:\n    _mri = float(mri_score)\nexcept NameError:\n    _mri = 0.72   # 시뮬레이션 기본값",
        "try:\n    _mri = float(today_mri)   # cell[11]에서 산출된 실시간 MRI\nexcept NameError:\n    _mri = 0.72"
    )
    new_src = new_src.replace(
        'try:\n    _cats = detected_categories   # Part 1 NLP 분류 결과\nexcept NameError:\n    _cats = ["지정학분쟁"]        # 시뮬레이션 기본값',
        'try:\n    _cats = [today_top_cat]   # cell[7]에서 분류된 최다 카테고리\nexcept NameError:\n    _cats = ["지정학분쟁"]'
    )
    cells[idx_hist]['source'] = [new_src]
    cells[idx_hist]['outputs'] = []
    cells[idx_hist]['execution_count'] = None
    print(f'historical_matcher 변수명 수정 (cell[{idx_hist}])')

# ─────────────────────────────────────────────────────────────
# STEP 3. cell[23] ODCY 추천 — 하드코딩 제거 + MRI 조건 + 화물유형 연동
# ─────────────────────────────────────────────────────────────

ODCY_NEW_SRC = [
    '# ── Step 3. 목적지 항만 주변 창고·ODCY 자동 탐색 ─────────────\n',
    '# MRI >= 0.5 (주의 이상)일 때만 실행됩니다.\n',
    '# 화주가 Step 1에서 입력한 정보를 그대로 사용합니다.\n',
    '# 카카오 API 키(.env)가 있으면 실데이터, 없으면 시뮬 DB 자동 사용.\n',
    'from src.odcy_recommender import recommend_storage, format_storage_message\n',
    '\n',
    'MRI_THRESHOLD = 0.5   # 주의 등급 이상일 때 창고 추천 활성화\n',
    '\n',
    'try:\n',
    '    _mri_now = today_mri\n',
    'except NameError:\n',
    '    _mri_now = 0.72\n',
    '\n',
    'try:\n',
    '    _cargo_enum  = CARGO_ENUM\n',
    '    _port        = DEPARTURE_PORT\n',
    '    _company     = SHIPPER_INPUT["company"]\n',
    '    _cbm         = SHIPPER_INPUT["cbm"]\n',
    '    _origin      = SHIPPER_INPUT["origin_address"]\n',
    '    _pickup      = SHIPPER_INPUT["pickup_date"]\n',
    '    _cargo_str   = SHIPPER_INPUT["cargo_type_str"]\n',
    'except NameError:\n',
    '    _cargo_enum  = CargoType.GENERAL\n',
    '    _port        = "부산항(북항)"\n',
    '    _company     = "테스트화주"\n',
    '    _cbm         = 15.0\n',
    '    _origin      = "경기도 수원시"\n',
    '    _pickup      = "2026-05-20"\n',
    '    _cargo_str   = "일반화물"\n',
    '\n',
    'print("=" * 60)\n',
    'print("Step 3. 창고·ODCY 자동 탐색")\n',
    'print("=" * 60)\n',
    'print(f"  현재 MRI: {_mri_now:.3f}  |  임계값: {MRI_THRESHOLD}")\n',
    '\n',
    'if _mri_now < MRI_THRESHOLD:\n',
    '    print(f"\\n  MRI {_mri_now:.3f} < {MRI_THRESHOLD} — 현재 창고 보관 불필요")\n',
    '    print("  평상시 운영: 기존 일정대로 CY 직반입을 권장합니다.")\n',
    '    result = None\n',
    'else:\n',
    '    grade_str = "위험" if _mri_now >= 0.8 else ("경계" if _mri_now >= 0.6 else "주의")\n',
    '    print(f"  MRI {_mri_now:.3f} [{grade_str}] — 창고·ODCY 탐색을 시작합니다.")\n',
    '    print(f"  화물 유형: {_cargo_str} | 항만: {_port} | {_cbm} CBM\\n")\n',
    '\n',
    '    kakao_key = os.getenv("KAKAO_REST_API_KEY", "")\n',
    '    mobi_key  = os.getenv("KAKAO_MOBILITY_KEY",  "")\n',
    '    mode_str  = "카카오 실데이터" if kakao_key else "시뮬레이션 DB"\n',
    '    print(f"  데이터 소스: {mode_str}")\n',
    '\n',
    '    result = recommend_storage(\n',
    '        port_name          = _port,\n',
    '        cargo_type         = _cargo_enum,\n',
    '        top_n              = 3,\n',
    '        kakao_rest_key     = kakao_key or None,\n',
    '        kakao_mobility_key = mobi_key  or None,\n',
    '    )\n',
    '\n',
    '    print(format_storage_message(result))\n',
    '\n',
    '    # 이후 셀에서 사용할 SCENARIO dict 자동 구성\n',
    '    SCENARIO = {\n',
    '        "port_name":   _port,\n',
    '        "cargo_type":  _cargo_enum,\n',
    '        "company":     _company,\n',
    '        "cbm":         _cbm,\n',
    '        "origin":      _origin,\n',
    '        "pickup_date": _pickup,\n',
    '        "mri_now":     _mri_now,\n',
    '        "cargo_type_str": _cargo_str,\n',
    '    }\n',
]

idx_odcy = find_cell('recommend_storage')
if idx_odcy is not None:
    cells[idx_odcy]['source'] = ODCY_NEW_SRC
    cells[idx_odcy]['outputs'] = []
    cells[idx_odcy]['execution_count'] = None
    print(f'ODCY 추천 셀 수정 (cell[{idx_odcy}])')

# ─────────────────────────────────────────────────────────────
# STEP 4. 4가지 옵션 셀 — 실제 지연일수 + MRI 조건 연동
# ─────────────────────────────────────────────────────────────

idx_opt = find_cell('option_presenter')
if idx_opt is not None:
    src = ''.join(cells[idx_opt]['source'])
    # MRI 조건 체크 + 실제 지연일수 사용
    new_src = src.replace(
        'try:\n    _shipment_in = SCENARIO\n    _delay       = 14\n    _freight     = int(_shipment_in[\'cbm\'] * 45)\nexcept NameError:\n    _shipment_in = {\'cargo_type\': \'일반화물\', \'cbm\': 15.0, \'region\': \'경기남부\'}\n    _delay, _freight = 14, 675',
        "# MRI 조건 체크\ntry:\n    _mri_check = today_mri\nexcept NameError:\n    _mri_check = 0.72\n\nif _mri_check < 0.5:\n    print(f'MRI {_mri_check:.3f} < 0.5 — 4가지 옵션 비교 불필요 (평상시)')\nelse:\n    # 시나리오별 지연일수 자동 결정\n    try:\n        from src.scenario_engine import auto_classify_scenario\n        from src.config import SCENARIOS\n        _sid   = auto_classify_scenario(_mri_check, today_top_cat)\n        _delay = SCENARIOS[_sid]['delay_days']\n    except Exception:\n        _delay = 14\n\n    try:\n        _shipment_in = SCENARIO\n        _freight = int(_shipment_in.get('cbm', 15) * 45)\n    except NameError:\n        _shipment_in = {'cargo_type': '일반화물', 'cbm': 15.0, 'region': '경기남부'}\n        _freight = 675\n\n    try:\n        _storage = result\n    except NameError:\n        from src.odcy_recommender import recommend_storage, CargoType\n        _storage = recommend_storage('부산항(북항)', CargoType.GENERAL, top_n=3)"
    )
    # try/except _storage 블록 제거 (위에서 이미 처리)
    new_src = new_src.replace(
        'try:\n    _storage = result                  # cell[23] recommend_storage() 결과\nexcept NameError:\n    from src.odcy_recommender import recommend_storage, CargoType\n    _storage = recommend_storage(\'부산항(북항)\', CargoType.GENERAL, top_n=3)',
        ''
    )
    cells[idx_opt]['source'] = [new_src]
    cells[idx_opt]['outputs'] = []
    cells[idx_opt]['execution_count'] = None
    print(f'4가지 옵션 셀 수정 (cell[{idx_opt}])')

# ─────────────────────────────────────────────────────────────
# STEP 5. 루티 JSON 셀 — 화주 입력 자동 연동
# ─────────────────────────────────────────────────────────────

idx_routy = find_cell('storage_routy_adapter')
if idx_routy is not None:
    src = ''.join(cells[idx_routy]['source'])
    # top_warehouse 가져오기 전에 result None 체크 추가
    if 'if result is None' not in src:
        guard = (
            '\n# MRI 조건 미충족 시 루티 JSON 건너뜀\n'
            'if result is None:\n'
            '    print("MRI가 임계값 미만 — 루티 JSON 생성 생략 (평상시 운영)")\n'
            'else:\n'
        )
        # from src.storage_routy_adapter import 바로 다음 줄에 guard 삽입
        new_src = src.replace(
            'from src.storage_routy_adapter import (',
            guard + 'from src.storage_routy_adapter import ('
        )
        # top_warehouse 이후 코드를 else 블록으로 들여쓰기
        # 간단하게: 전체 블록을 if/else로 감싸는 대신 guard 후 전체를 indented
        # 위 방식으로 충분 (result None이면 import만 되고 실행 안됨은 안되므로)
        # 더 안전하게: generate_storage_routy_json 호출 전에 체크
        src_lines = src.split('\n')
        new_lines = []
        inside_block = False
        for line in src_lines:
            if 'top_warehouse = result' in line:
                new_lines.append('')
                new_lines.append('if result is None:')
                new_lines.append("    print('MRI 임계값 미만 — 루티 JSON 생성 생략')")
                new_lines.append('else:')
                inside_block = True
            if inside_block:
                new_lines.append('    ' + line if line.strip() else line)
            else:
                new_lines.append(line)
        cells[idx_routy]['source'] = ['\n'.join(new_lines)]
        cells[idx_routy]['outputs'] = []
        cells[idx_routy]['execution_count'] = None
        print(f'루티 JSON 셀 수정 (cell[{idx_routy}])')
    else:
        print(f'루티 JSON 셀 이미 수정됨 (cell[{idx_routy}])')

# ─────────────────────────────────────────────────────────────
# 저장
# ─────────────────────────────────────────────────────────────
with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print('\n모든 패치 완료. 저장됨.')
print(f'총 셀 수: {len(cells)}')
