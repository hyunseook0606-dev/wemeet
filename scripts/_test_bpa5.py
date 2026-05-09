# -*- coding: utf-8 -*-
import sys, os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

import requests

API_KEY = os.environ.get('BPA_API_KEY', '')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

ENDPOINTS = [
    'https://api.odcloud.kr/api/15055478/v1/uddi:41e6ef8e-f559-46e5-baf4-849b7b61565a_201910221534',
    'https://api.odcloud.kr/api/15055478/v1/uddi:0f15fa04-2394-47ad-a1f8-820260eaf4c5',
    'https://api.odcloud.kr/api/15055478/v1/uddi:57d4ac51-57f4-460d-878a-8f8884deb2d6',
    'https://api.odcloud.kr/api/15055478/v1/uddi:efd6b404-4425-452f-a9db-a38436ee59b9',
    'https://api.odcloud.kr/api/15055478/v1/uddi:6668fa12-2691-47d4-9e1c-d6e415c6fc52',
    'https://api.odcloud.kr/api/15055478/v1/uddi:80709ec8-4d80-4407-8cc8-fafbea21766a',
]

for i, base_url in enumerate(ENDPOINTS, 1):
    uddi = base_url.split('uddi:')[-1][:8]  # 앞 8자리만 표시
    params = {'serviceKey': API_KEY, 'page': 1, 'perPage': 3}
    try:
        r = requests.get(base_url, params=params, headers=HEADERS, timeout=10)
        print(f'[{i}] uddi:{uddi}... → HTTP {r.status_code}')
        if r.status_code == 200:
            try:
                d = r.json()
                total = d.get('totalCount', '?')
                rows  = d.get('data', [])
                print(f'    totalCount: {total}')
                if rows:
                    print(f'    컬럼: {list(rows[0].keys())}')
                    print(f'    샘플 1행: {rows[0]}')
                else:
                    print(f'    data 없음. 키: {list(d.keys())}')
            except Exception as e:
                print(f'    JSON 파싱 오류: {e}')
                print(f'    응답: {r.text[:200]}')
        else:
            print(f'    응답: {r.text[:120]}')
    except Exception as e:
        print(f'    예외: {e}')
    print()
