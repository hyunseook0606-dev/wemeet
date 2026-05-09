# -*- coding: utf-8 -*-
"""BPA API — 데이터셋 리소스 목록 + 파일다운로드 형식 시도"""
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

# ── 데이터셋 ID 목록 (관련 가능 ID) ──────────────────────────────────────
DATASET_IDS = ['15055478', '15056691', '15049952', '15058261', '15065022']

print('=== odcloud 데이터셋 리소스 목록 조회 ===')
for ds_id in DATASET_IDS:
    url = f'https://api.odcloud.kr/api/{ds_id}/v1'
    params = {'serviceKey': API_KEY, 'page': 1, 'perPage': 1}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=8)
        if r.status_code != 404:
            print(f'[{r.status_code}] 데이터셋 {ds_id}: {r.text[:200]}')
    except Exception as e:
        pass

print()
print('=== 공공데이터포털 데이터셋 파일 메타데이터 ===')
# data.go.kr REST API로 데이터셋 정보 조회
meta_url = 'https://www.data.go.kr/api/3/datasets/15055478'
try:
    r = requests.get(meta_url, headers=HEADERS, timeout=8)
    print(f'[{r.status_code}] {meta_url}')
    print(r.text[:400])
except Exception as e:
    print(f'예외: {e}')

print()
print('=== 직접 파일 다운로드 형식 시도 (fileDataDetailPk) ===')
# 파일형 데이터셋의 경우 아래 형식으로 다운로드
file_urls = [
    f'https://api.odcloud.kr/api/15055478/v1?serviceKey={API_KEY}&type=json&page=1&perPage=5',
    f'https://api.odcloud.kr/api/15055478/v1?serviceKey={API_KEY}&type=csv',
    'https://api.odcloud.kr/api/15055478/v1/uddi:f35a0b34-fc7c-44cf-a04a-afb2d2e5a15c?serviceKey='
    + API_KEY + '&type=json&page=1&perPage=3',
]
for url in file_urls:
    masked = url.replace(API_KEY, mask_key(API_KEY) if False else '***KEY***')
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        print(f'[{r.status_code}] ...{url[-50:]}')
        if r.status_code == 200:
            ct = r.headers.get('Content-Type','')
            print(f'  Content-Type: {ct}')
            print(f'  응답: {r.text[:300]}')
        else:
            print(f'  응답: {r.text[:100]}')
    except Exception as e:
        print(f'  예외: {e}')
    print()

print()
print('=== 핵심: API 활용가이드 PDF에서 확인해야 할 정보 ===')
print('data.go.kr 로그인 → 마이페이지 → 활용신청 목록 →')
print('"부산항만공사_부산항 컨테이너 수송통계" 상세보기 →')
print('"활용가이드" 다운로드 → PDF에서 엔드포인트 URL 확인')
