# -*- coding: utf-8 -*-
"""BPA API — 실제 작동하는 엔드포인트 탐색 최종"""
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
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

print(f'API 키: {"*"*20}...{API_KEY[-6:]}')
print()

# ── apis.data.go.kr 500 에러 상세 분석 ───────────────────────────────
# 500이 뜬다는 건 경로가 존재할 수 있음 → 파라미터 변경 시도
print('=== 500 에러 상세 파악 (파라미터 조합 변경) ===')

base = 'https://apis.data.go.kr/B551177/BusanContainerShip'
paths = [
    '/getBusanContainerShipList',
    '/getContainerMonthly',
    '/getBpaContainerStats',
    '/getBusanPortContainerList',
]

for path in paths:
    url = base + path
    # XML 형식 시도
    for fmt in ['json', 'xml']:
        params = {
            'serviceKey': API_KEY,
            'numOfRows': '5',
            'pageNo': '1',
            'resultType': fmt,
        }
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=6)
            if r.status_code not in (404, 500):
                print(f'[{r.status_code}] {path} ({fmt})')
                print(f'  {r.text[:200]}')
        except Exception:
            pass

# ── 가장 흔한 data.go.kr BPA 패턴 ────────────────────────────────────
print()
print('=== 알려진 BPA API 패턴 직접 시도 ===')
known_urls = [
    # 공공데이터포털에 실제 등록된 BPA 서비스들
    'https://apis.data.go.kr/B551177/busanContainerSend/getBusanContainerSendList',
    'https://apis.data.go.kr/B551177/BpaContainerSend/getBpaContainerSendList',
    'https://apis.data.go.kr/B551177/BusanPortStat/getBusanContainerStat',
    'https://apis.data.go.kr/B551177/busanContainerYear/getBusanContainerYearList',
]

for url in known_urls:
    params = {
        'serviceKey': API_KEY,
        'numOfRows': 5,
        'pageNo': 1,
        'type': 'json',
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=8)
        short_url = url.split('B551177/')[-1]
        if r.status_code == 200:
            print(f'[200] ★ 성공! {short_url}')
            print(f'  응답: {r.text[:400]}')
        elif r.status_code != 404:
            print(f'[{r.status_code}] {short_url}')
            print(f'  {r.text[:100]}')
    except Exception as e:
        pass

print()
print('=' * 55)
print('결론: 아래 방법으로 실제 엔드포인트 URL을 확인하세요.')
print()
print('① data.go.kr 로그인')
print('② 마이페이지 → 오픈API → 활용신청 목록')
print('③ "부산항만공사_부산항 컨테이너 수송통계" 클릭')
print('④ "활용가이드" 또는 "API 명세서" 탭 클릭')
print('⑤ 거기에 적힌 URL(예: https://apis.data.go.kr/...)')
print('   그 URL을 이 대화창에 붙여넣어주세요.')
print('=' * 55)
