# -*- coding: utf-8 -*-
"""BPA API 연동 테스트 — API 키 노출 없이 결과만 출력"""
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
if not API_KEY:
    print('BPA_API_KEY 미설정 — .env 확인 필요')
    sys.exit(1)

print(f'API 키 로드: {"*" * 8}...{API_KEY[-6:]}  (마지막 6자리만 표시)')
print()

# 공공데이터포털 odcloud 엔드포인트 후보들
ENDPOINTS = [
    # 데이터셋 15055478 (부산항 컨테이너 수송통계)
    'https://api.odcloud.kr/api/15055478/v1/uddi:f35a0b34-fc7c-44cf-a04a-afb2d2e5a15c',
    'https://api.odcloud.kr/api/15055478/v1/uddi:2df50e23-4c48-4455-9a16-38406e94b5b8',
    'https://api.odcloud.kr/api/15055478/v1',
    # 데이터셋 15056691
    'https://api.odcloud.kr/api/15056691/v1/uddi:7b3c0a1e-5f2d-4c8b-9e1a-2f3a4b5c6d7e',
    'https://api.odcloud.kr/api/15056691/v1',
    # 공공데이터포털 기본 형식
    'https://apis.data.go.kr/B551177/BPAContainerStatistics/getContainerStatistics',
    'https://apis.data.go.kr/B551177/BpaContainerSend/getBpaContainerSendList',
]

HEADERS = {'User-Agent': 'Mozilla/5.0'}

success_found = False

for url in ENDPOINTS:
    params = {
        'serviceKey': API_KEY,
        'page': 1,
        'perPage': 5,
        'returnType': 'JSON',
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        ct = resp.headers.get('Content-Type', '')
        print(f'[{resp.status_code}] {url.split("/api/")[-1][:60]}')

        if resp.status_code == 200 and 'json' in ct:
            try:
                data = resp.json()
                # 응답 구조 파악
                if isinstance(data, dict):
                    keys = list(data.keys())
                    print(f'  JSON 키: {keys}')
                    # 데이터 rows 추출
                    rows = (data.get('data') or
                            data.get('items') or
                            data.get('response', {}).get('body', {}).get('items', []))
                    if rows and isinstance(rows, list) and len(rows) > 0:
                        print(f'  데이터 행 수: {len(rows)} (전체: {data.get("totalCount", "?")})')
                        print(f'  첫 번째 행 컬럼: {list(rows[0].keys())}')
                        print(f'  첫 번째 행 값: {rows[0]}')
                        success_found = True
                        print()
                        print('>>> 연결 성공! 전체 데이터 조회 중...')
                        # 전체 데이터 가져오기 (perPage=1000)
                        params['perPage'] = 1000
                        resp2 = requests.get(url, params=params, headers=HEADERS, timeout=15)
                        data2 = resp2.json()
                        all_rows = (data2.get('data') or
                                    data2.get('items') or
                                    data2.get('response', {}).get('body', {}).get('items', []))
                        if all_rows:
                            print(f'  전체 행 수: {len(all_rows)}')
                            # 연도/월 컬럼 찾기
                            sample = all_rows[0]
                            year_col = next((k for k in sample if any(x in k.lower() for x in ['year','연도','기준년','년도'])), None)
                            month_col = next((k for k in sample if any(x in k.lower() for x in ['month','월','기준월'])), None)
                            teu_col = next((k for k in sample if any(x in k.lower() for x in ['teu','컨테이너','container'])), None)
                            print(f'  연도 컬럼: {year_col}')
                            print(f'  월 컬럼: {month_col}')
                            print(f'  TEU 컬럼: {teu_col}')
                            if year_col:
                                years = sorted(set(str(r.get(year_col,'')) for r in all_rows if r.get(year_col)))
                                print(f'  연도 범위: {years[0]} ~ {years[-1]} ({len(years)}개년)')
                            if month_col:
                                print('  → 월별 데이터 있음!')
                            else:
                                print('  → 월 컬럼 없음 (연도별만 있을 수 있음)')
                            # 첫 3행 출력
                            print('  샘플 (첫 3행):')
                            for row in all_rows[:3]:
                                print(f'    {row}')
                        break
                    else:
                        total = data.get('totalCount', data.get('total', '?'))
                        print(f'  데이터 없음 (totalCount={total})')
                        if 'resultCode' in data or 'returnAuthMsg' in data:
                            print(f'  오류 메시지: {data.get("returnAuthMsg", data.get("resultMsg", ""))}')
            except json.JSONDecodeError:
                print(f'  JSON 파싱 실패, 응답: {resp.text[:100]}')
        elif resp.status_code == 200:
            print(f'  Content-Type: {ct} (JSON 아님)')
            print(f'  응답 앞부분: {resp.text[:150]}')
        else:
            print(f'  오류 응답: {resp.text[:100]}')
    except Exception as e:
        print(f'  예외: {e}')
    print()

if not success_found:
    print('=' * 50)
    print('모든 엔드포인트 실패.')
    print('data.go.kr 활용신청 상세 페이지에서 실제 엔드포인트 URL을 확인해주세요.')
    print('API 문서 URL: https://www.data.go.kr/data/15055478/openapi.do')
