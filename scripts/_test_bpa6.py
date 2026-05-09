# -*- coding: utf-8 -*-
"""BPA 연도별 전체 데이터 확인 — 5번·6번 엔드포인트"""
import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

import requests
import pandas as pd

API_KEY = os.environ.get('BPA_API_KEY', '')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

EP5 = 'https://api.odcloud.kr/api/15055478/v1/uddi:6668fa12-2691-47d4-9e1c-d6e415c6fc52'
EP6 = 'https://api.odcloud.kr/api/15055478/v1/uddi:80709ec8-4d80-4407-8cc8-fafbea21766a'

for label, url in [('5번 (연도/전체)', EP5), ('6번 (년도/합계)', EP6)]:
    r = requests.get(url, params={'serviceKey': API_KEY, 'page': 1, 'perPage': 100}, headers=HEADERS, timeout=10)
    rows = r.json().get('data', [])
    year_col = '연도' if '연도' in rows[0] else '년도'
    total_col = '전체' if '전체' in rows[0] else '합계'
    df = pd.DataFrame(rows)[[year_col, total_col]].rename(columns={year_col: '연도', total_col: '전체TEU'})
    df = df.sort_values('연도').reset_index(drop=True)
    df['월평균(만TEU)'] = (df['전체TEU'] / 12 / 10000).round(1)
    print(f'=== {label} ===')
    print(f'연도 범위: {df["연도"].min()} ~ {df["연도"].max()} ({len(df)}개년)')
    print()
    print(df[df['연도'] >= 2015].to_string(index=False))
    print()
