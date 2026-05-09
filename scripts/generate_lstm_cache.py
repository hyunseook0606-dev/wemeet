"""
scripts/generate_lstm_cache.py
로컬에서 LSTM을 학습한 뒤 data/lstm_cache.json 에 저장합니다.
서버(Render)는 torch 없이 이 파일을 읽어 실제 LSTM 결과를 반환합니다.

실행:
    python scripts/generate_lstm_cache.py
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from src.lstm_forecaster import build_main_df, train_and_forecast, HORIZON
from src.mri_engine import build_mri_series

print("LSTM 학습 시작 (약 1~2분 소요)...")

dates = pd.date_range('2020-01-01', '2026-04-01', freq='MS')
mri_s = build_mri_series(dates)
mdf   = build_main_df(dates, mri_s)

result = train_and_forecast(mdf, epochs=60)

labels = pd.date_range('2026-04-01', periods=HORIZON, freq='MS')
cache = {
    'generated_at': datetime.now().isoformat(),
    'mape': round(result['mape_3m'], 2),
    'source': 'lstm_cached',
    'forecast': [
        {'month': l.strftime('%Y.%m'), 'teu_10k': round(float(v), 2)}
        for l, v in zip(labels, result['future_real'])
    ],
}

out_path = ROOT / 'data' / 'lstm_cache.json'
out_path.parent.mkdir(exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"저장 완료: {out_path}")
print(f"  MAPE  : {cache['mape']}%")
print(f"  예측값: {cache['forecast']}")
print()
print("다음 단계:")
print("  git add data/lstm_cache.json")
print("  git commit -m 'update lstm cache'")
print("  git push")
