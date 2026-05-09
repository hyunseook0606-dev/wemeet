"""
scripts/geocode_nlic.py
NLIC(국가물류통합정보센터) 부산 물류창고 데이터를 지오코딩해서
data/nlic_warehouses.json 으로 저장합니다.

실행:
    python scripts/geocode_nlic.py

결과: data/nlic_warehouses.json (좌표 포함 창고 목록)
"""
from __future__ import annotations

import os, sys, json, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

import pandas as pd
import requests

KAKAO_KEY = os.getenv('KAKAO_REST_API_KEY', '')
XLS_PATH  = ROOT / '부산_물류창고정보_260509.xls'
OUT_PATH  = ROOT / 'data' / 'nlic_warehouses.json'

# NLIC 취급화물 → cargo_types 매핑
_CARGO_MAP = {
    '물류시설법':        ['일반화물'],
    '물류시설법(그레이)': ['일반화물'],
    '수산물':            ['냉동화물', '냉장화물'],
    '화약류취급가능':    ['위험물'],
    '가공식품류':        ['냉장화물', '일반화물'],
    '냉동식품류':        ['냉동화물'],
    '생활용품창고':      ['일반화물'],
}

def geocode(address: str) -> tuple[float, float] | None:
    """카카오 주소검색 API로 주소 → (lat, lng) 변환."""
    if not KAKAO_KEY:
        return None
    try:
        resp = requests.get(
            'https://dapi.kakao.com/v2/local/search/address.json',
            headers={'Authorization': f'KakaoAK {KAKAO_KEY}'},
            params={'query': address, 'size': 1},
            timeout=5,
        )
        docs = resp.json().get('documents', [])
        if docs:
            return float(docs[0]['y']), float(docs[0]['x'])
    except Exception:
        pass
    return None


def infer_cargo_types(row: dict) -> list[str]:
    """면적 컬럼 + 취급화물 문자열로 지원 화물 유형 추론."""
    types: set[str] = set()

    base = _CARGO_MAP.get(str(row.get('cargo_type', '')).strip(), ['일반화물'])
    types.update(base)

    if float(row.get('area_cold', 0) or 0) > 0:
        types.update(['냉장화물', '냉동화물'])
    if float(row.get('area_hazmat', 0) or 0) > 0:
        types.add('위험물')

    notes = str(row.get('notes', '')).lower()
    if any(k in notes for k in ['냉동', '냉장', '저온', '수산']):
        types.update(['냉장화물', '냉동화물'])
    if any(k in notes for k in ['위험물', '화약', '배터리', '2차전지']):
        types.add('위험물')
    if any(k in notes for k in ['전자', '반도체', '디스플레이']):
        types.add('전자제품')

    return sorted(types)


def main() -> None:
    if not KAKAO_KEY:
        print('[ERROR] KAKAO_REST_API_KEY 없음 -- .env 확인 후 재실행')
        sys.exit(1)

    print(f'[INFO] 파일 읽는 중: {XLS_PATH.name}')
    df = pd.read_excel(XLS_PATH, engine='xlrd')
    df.columns = ['name','biz_no','address','area_general','area_cold',
                  'area_hazmat','area_tower','cargo_type','notes']
    df = df.fillna(0)
    df['name']    = df['name'].astype(str).str.strip()
    df['address'] = df['address'].astype(str).str.strip()
    print(f'  총 {len(df)}개 창고 로드')

    results: list[dict] = []
    failed = 0

    for i, row in df.iterrows():
        coords = geocode(row['address'])
        if coords is None:
            failed += 1
            continue

        lat, lng = coords
        total_area = (
            float(row['area_general'] or 0)
            + float(row['area_cold']    or 0)
            + float(row['area_hazmat']  or 0)
            + float(row['area_tower']   or 0)
        )

        results.append({
            'id':           f'NLIC{i+1:04d}',
            'name':         row['name'],
            'address':      row['address'],
            'phone':        '',
            'lat':          lat,
            'lng':          lng,
            'type':         '물류창고(NLIC)',
            'area_sqm':     round(total_area, 1),
            'area_general': float(row['area_general'] or 0),
            'area_cold':    float(row['area_cold']    or 0),
            'area_hazmat':  float(row['area_hazmat']  or 0),
            'cold_chain':   float(row['area_cold'] or 0) > 0,
            'hazmat_license': float(row['area_hazmat'] or 0) > 0,
            'bonded':       True,
            'cargo_types':  infer_cargo_types(row.to_dict()),
            'notes':        str(row['notes']).strip(),
            'source':       'NLIC',
        })

        if (i + 1) % 50 == 0:
            print(f'  {i+1}/{len(df)} 완료 (성공 {len(results)}, 실패 {failed})')
        time.sleep(0.05)   # 과부하 방지

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'\n[OK] 저장 완료: {OUT_PATH}')
    print(f'   지오코딩 성공: {len(results)}개 / 실패: {failed}개')
    cold   = sum(1 for r in results if r['cold_chain'])
    hazmat = sum(1 for r in results if r['hazmat_license'])
    print(f'   냉동냉장 설비: {cold}개 / 위험물 허가: {hazmat}개')


if __name__ == '__main__':
    main()
