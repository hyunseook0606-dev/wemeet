# -*- coding: utf-8 -*-
import logging, json, subprocess, sys
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.WARNING)
DATA_DIR = Path('data')

print('=== 1. load_oil_price() ===')
from src.data_loader import load_oil_price
df = load_oil_price(DATA_DIR)
if df is not None:
    print(f'  OK: {len(df)}개월, 최신={df["date"].iloc[-1].strftime("%Y.%m")} / ${df["oil_price"].iloc[-1]:.2f}')
else:
    print('  None (시뮬 폴백)')

print()
print('=== 2. today_rates.json ===')
fp = DATA_DIR / 'today_rates.json'
if fp.exists():
    d = json.loads(fp.read_text(encoding='utf-8'))
    k = sorted(d.keys())[-1]
    print(f'  {k}: 환율={d[k].get("usd_krw")}원, 유가=${d[k].get("brent_usd")}')
else:
    print('  없음')

print()
print('=== 3. auto_update --mode daily ===')
r = subprocess.run([sys.executable, '-X', 'utf8', 'scripts/auto_update.py', '--mode', 'daily'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
for line in r.stdout.strip().split('\n'):
    if line.strip():
        print(' ', line)

print()
print('=== 4. oil_monthly.csv ===')
cache_fp = DATA_DIR / 'ecos_cache' / 'oil_monthly.csv'
if cache_fp.exists():
    df2 = pd.read_csv(cache_fp, encoding='utf-8-sig')
    df2['date'] = pd.to_datetime(df2['date'])
    print(f'  OK: {len(df2)}개월, 최신={df2["date"].iloc[-1].strftime("%Y.%m")} / ${df2["oil_price"].iloc[-1]:.2f}')
    print('  최근 4개월:')
    for _, row in df2.tail(4).iterrows():
        print(f'    {row["date"].strftime("%Y.%m")}: ${row["oil_price"]:.2f}')
else:
    print('  미생성')
