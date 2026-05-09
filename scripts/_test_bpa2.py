# -*- coding: utf-8 -*-
"""BPA API 엔드포인트 탐색 — odcloud 메타데이터 + 다양한 URL 패턴 시도"""
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
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

def mask(key):
    return f'{"*"*8}...{key[-6:]}'

print(f'API 키: {mask(API_KEY)}')
print()

# ── 방법 1: odcloud 메타데이터 API로 실제 리소스 ID 조회 ────────────────
print('=== [1] odcloud 데이터셋 메타데이터 조회 ===')
meta_urls = [
    'https://api.odcloud.kr/api/15055478/v1',
    'https://api.odcloud.kr/api/15055478',
]
for url in meta_urls:
    try:
        # 메타데이터는 인증 없이 접근 시도
        r = requests.get(url, headers=HEADERS, timeout=8)
        print(f'  [{r.status_code}] {url}')
        if r.status_code == 200:
            try:
                d = r.json()
                print(f'  응답: {json.dumps(d, ensure_ascii=False)[:300]}')
            except:
                print(f'  응답(텍스트): {r.text[:200]}')
    except Exception as e:
        print(f'  예외: {e}')

print()

# ── 방법 2: 인증키 포함 odcloud 다양한 파라미터 형식 ─────────────────────
print('=== [2] odcloud serviceKey 다양한 방식 ===')
dataset_id = '15055478'
test_configs = [
    # (URL, params)
    (
        f'https://api.odcloud.kr/api/{dataset_id}/v1',
        {'serviceKey': API_KEY, 'page': 1, 'perPage': 3}
    ),
    (
        f'https://api.odcloud.kr/api/{dataset_id}/v1',
        {'Authorization': f'Infuser {API_KEY}', 'page': 1, 'perPage': 3}
    ),
]

for url, params in test_configs:
    # Authorization 헤더 방식인 경우
    if 'Authorization' in params:
        h = {**HEADERS, 'Authorization': params.pop('Authorization')}
        r = requests.get(url, params=params, headers=h, timeout=8)
    else:
        r = requests.get(url, params=params, headers=HEADERS, timeout=8)
    print(f'  [{r.status_code}] {url}')
    print(f'  응답: {r.text[:250]}')
    print()

# ── 방법 3: apis.data.go.kr — 올바른 서비스 경로 탐색 ─────────────────
print('=== [3] apis.data.go.kr BPA 서비스 경로 탐색 ===')
# BPA 기관코드: B551177 또는 다른 코드
api_paths = [
    '/B551177/busanContainerShipping/getContainerShippingList',
    '/B551177/busanContainerShipping/getBusanContainerList',
    '/B551177/BusanPort/getContainerStats',
    '/B551177/BusanPortContainer/getList',
    '/1480000/BusanPortContainer/getContainerList',
    '/6240000/BusanContainer/getList',
]
for path in api_paths:
    url = f'https://apis.data.go.kr{path}'
    params = {'serviceKey': API_KEY, 'numOfRows': 3, 'pageNo': 1, 'type': 'json'}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=8)
        if r.status_code != 404:
            print(f'  [{r.status_code}] {path}')
            print(f'  응답: {r.text[:200]}')
            print()
    except Exception as e:
        pass

# ── 방법 4: 직접 data.go.kr OpenAPI 스펙 확인 ─────────────────────────
print('=== [4] data.go.kr REST API 스펙 조회 ===')
spec_url = f'https://www.data.go.kr/cmm/cmm/selectRestApiInfo.do?publicDataPk={dataset_id}'
try:
    r = requests.get(spec_url, headers=HEADERS, timeout=8)
    print(f'  [{r.status_code}] spec URL')
    if r.status_code == 200:
        print(f'  응답: {r.text[:400]}')
except Exception as e:
    print(f'  예외: {e}')
