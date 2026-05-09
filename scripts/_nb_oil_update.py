# -*- coding: utf-8 -*-
"""노트북 유가 관련 셀 업데이트 스크립트"""
import json
from pathlib import Path

NB = Path('notebooks/wemeet_v4_main.ipynb')

with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

def code_cell(src):
    return {'cell_type': 'code', 'metadata': {}, 'source': src,
            'outputs': [], 'execution_count': None}

def md_cell(src):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': src}

# ── Cell 3: 데이터 현황 (auto_update 스케줄 텍스트 수정) ─────────────────────
CELL3 = (
    "# 0-2. 데이터 소스 전체 현황\n"
    "from src.real_data_fetcher import print_data_status\n"
    "print_data_status()\n"
    "\n"
    "print('\\n[운임지수 XLS 파일]')\n"
    "freight_dir = DATA_DIR / 'freight_index'\n"
    "freight_dir.mkdir(exist_ok=True)\n"
    "xls_files = list(freight_dir.glob('*.xls')) + list(freight_dir.glob('*.xlsx'))\n"
    "kcci_csv  = DATA_DIR / 'kcci_weekly.csv'\n"
    "if xls_files:\n"
    "    print(f'  XLS: {len(xls_files)}개 확인')\n"
    "    for f in xls_files[:3]: print(f'    - {f.name}')\n"
    "else:\n"
    "    print('  XLS: 없음')\n"
    "    print('    -> data/freight_index/ 에 저장 후:')\n"
    "    print('       python scripts/auto_update.py --combine-freight')\n"
    "if kcci_csv.exists():\n"
    "    import pandas as _pd\n"
    "    _k = _pd.read_csv(kcci_csv, encoding='utf-8-sig')\n"
    "    print(f'  kcci_weekly.csv: {len(_k)}주 (합치기 완료)')\n"
    "else:\n"
    "    print('  kcci_weekly.csv: 미생성 -> --combine-freight 실행')\n"
    "\n"
    "# 오늘 환율·유가 표시 (auto_update.py --mode daily 실행 결과)\n"
    "import json as _json\n"
    "rates_fp = DATA_DIR / 'today_rates.json'\n"
    "if rates_fp.exists():\n"
    "    _rates = _json.loads(rates_fp.read_text(encoding='utf-8'))\n"
    "    _today_key = sorted(_rates.keys())[-1]\n"
    "    _d = _rates[_today_key]\n"
    "    print(f'\\n[오늘 자동수집 실데이터] ({_today_key})')\n"
    "    if 'usd_krw' in _d: print(f'  환율: {_d[\"usd_krw\"]:,.0f}원/달러  [frankfurter.app]')\n"
    "    if 'brent_usd' in _d: print(f'  유가: ${_d[\"brent_usd\"]:.2f}/배럴 (Brent)  [Yahoo Finance]')\n"
    "else:\n"
    "    print('\\n[자동수집] today_rates.json 없음 → auto_update.py 실행 필요')\n"
    "\n"
    "print('\\n[자동 갱신 스케줄]')\n"
    "print('  매일  08:30   환율 (frankfurter.app) + 유가 (Yahoo Finance BZ=F)')\n"
    "print('  매주 월 09:00  운임지수 (XLS 폴더 감시 + 합치기)')\n"
    "print('  매월  2일 09:30 물동량 (NLIC 자동 시도)')\n"
    "print('  등록: .\\\\scripts\\\\setup_scheduler.ps1')\n"
)

# ── Cell 15: 거시경제 수집 (load_oil_price 사용, 소스 레이블 수정) ───────────
CELL15 = (
    "# 3-4. 거시경제 데이터 수집\n"
    "# [LSTM 입력] 각 월의 실제값이 그대로 입력됩니다.\n"
    "#   예) 2025.05: 1390원, 2025.06: 1402원, ..., 2026.04: 1477원\n"
    "#   전체 평균(~1295원)이 아닙니다.\n"
    "from src.data_loader import load_throughput, load_oil_price\n"
    "from src.real_data_fetcher import (\n"
    "    fetch_bpa_throughput, fetch_ecos_exchange_rate,\n"
    "    fetch_exchange_rate_monthly, fetch_ecos_oil_price,\n"
    ")\n"
    "from src.lstm_forecaster import build_main_df\n"
    "import json as _json\n"
    "\n"
    "# ── 부산항 물동량 ──────────────────────────────────────\n"
    "throughput_df  = load_throughput(DATA_DIR, use_real=True) or fetch_bpa_throughput(start_year=2020)\n"
    "_csv_ok        = (DATA_DIR / 'busan_throughput.csv').exists()\n"
    "throughput_src = ('실데이터 (CSV)' if throughput_df is not None and _csv_ok else\n"
    "                  'BPA API' if throughput_df is not None else '시뮬')\n"
    "\n"
    "# ── 환율: ECOS 공식 → frankfurter.app 자동 폴백 ──────\n"
    "fx_ecos = fetch_ecos_exchange_rate('202001', cache_dir=CACHE_DIR)\n"
    "if fx_ecos is not None:\n"
    "    fx_df, fx_src = fx_ecos, 'ECOS 한국은행 (공식)'\n"
    "else:\n"
    "    fx_df = fetch_exchange_rate_monthly(start='2020-01-01')\n"
    "    fx_src = 'frankfurter.app (일별 자동수집)' if fx_df is not None else '시뮬'\n"
    "\n"
    "# ── 유가: Yahoo Finance BZ=F 월봉 (일별 자동수집) ────\n"
    "# 1순위: ecos_cache/oil_monthly.csv (auto_update 일별 갱신본)\n"
    "# 2순위: Yahoo Finance 라이브 fetch\n"
    "# 3순위: ECOS 두바이유 (API 키 필요)\n"
    "oil_df = load_oil_price(DATA_DIR, use_real=True)\n"
    "if oil_df is not None:\n"
    "    oil_src = 'Yahoo Finance Brent (일별 자동수집)'\n"
    "else:\n"
    "    oil_ecos = fetch_ecos_oil_price('202001', cache_dir=CACHE_DIR)\n"
    "    if oil_ecos is not None:\n"
    "        oil_df, oil_src = oil_ecos, 'ECOS 두바이유 (공식)'\n"
    "    else:\n"
    "        oil_df, oil_src = None, '시뮬'\n"
    "\n"
    "# ── 통합 DataFrame ──────────────────────────────────\n"
    "main_df = build_main_df(\n"
    "    dates, mri_series,\n"
    "    throughput_df=throughput_df,\n"
    "    exchange_rate_df=fx_df,\n"
    "    oil_price_df=oil_df,\n"
    ")\n"
    "\n"
    "latest    = main_df.iloc[-1]\n"
    "latest_ym = latest['date'].strftime('%Y.%m')\n"
    "\n"
    "# today_rates.json에서 오늘 실시간 유가 표시\n"
    "_rates_fp = DATA_DIR / 'today_rates.json'\n"
    "_today_oil = None\n"
    "if _rates_fp.exists():\n"
    "    _rd = _json.loads(_rates_fp.read_text(encoding='utf-8'))\n"
    "    _lk = sorted(_rd.keys())[-1]\n"
    "    _today_oil = _rd[_lk].get('brent_usd')\n"
    "\n"
    "print(f'통합 데이터: {len(main_df)}개월 (2020.01 ~ {latest_ym})')\n"
    "print()\n"
    "print('[데이터 소스]')\n"
    "print(f'  물동량: {throughput_src}')\n"
    "print(f'  환율:   {fx_src}')\n"
    "print(f'  유가:   {oil_src}')\n"
    "if _today_oil:\n"
    "    print(f'         (오늘 실시간: ${_today_oil:.2f}/배럴  [Yahoo Finance])')\n"
    "print()\n"
    "print(f'[최신 실제값 ({latest_ym}) - LSTM 예측 기준점]')\n"
    "print(f'  물동량: {latest[\"throughput\"]:.1f}만 TEU')\n"
    "print(f'  환율:   {latest[\"exchange_rate\"]:.0f}원/달러')\n"
    "print(f'  유가:   ${latest[\"oil_price\"]:.1f}/배럴')\n"
    "if _today_oil:\n"
    "    print(f'         (오늘 Yahoo Finance: ${_today_oil:.2f}/배럴)')\n"
    "print(f'  MRI:    {latest[\"mri\"]:.4f}')\n"
    "print()\n"
    "print('[최근 6개월 추이 - 이 값들이 LSTM에 그대로 입력됨]')\n"
    "recent = main_df.tail(6)[['date','throughput','exchange_rate','oil_price']].copy()\n"
    "recent['date'] = recent['date'].dt.strftime('%Y.%m')\n"
    "recent.columns = ['월','물동량(만TEU)','환율(원)','유가($)']\n"
    "print(recent.to_string(index=False))\n"
    "if throughput_src == '시뮬':\n"
    "    print('\\n★ 실데이터: https://nlic.go.kr/nlic/seaHarborGtqy.action')\n"
    "    print('  data/nlic_raw/ 저장 후: python scripts/auto_update.py --combine-nlic')\n"
    "main_df.tail(3)\n"
)

# ── Part 3 Markdown: Step 1 유가 설명 업데이트 ───────────────────────────────
# part3-md (cell 14)에서 유가 소스 설명 업데이트
CELL14_PATCH = {
    'old': '  최솟값 $48 -> 0.0  /  최댓값 $95 -> 1.0\n  $84.1 = ($84.1-$48)/($95-$48) = 0.768',
    'new': (
        '  최솟값 $48 -> 0.0  /  최댓값 $115 -> 1.0\n'
        '  $84.1 = ($84.1-$48)/($115-$48) = 0.539\n'
        '  $107.7 = ($107.7-$48)/($115-$48) = 0.891  <- Yahoo Finance 오늘값'
    )
}
CELL14_PATCH2 = {
    'old': '2026.04    196          1.7%      1477      82.3     0.24  <- 최신 실제값',
    'new': '2026.04    196          1.7%      1477     107.7     0.24  <- 최신 실제값 (Yahoo)'
}

# ── print_data_status: 자동수집 섹션 텍스트 수정 ────────────────────────────
# real_data_fetcher.py의 print_data_status() 출력 문자열도 업데이트

# ── 노트북 패치 적용 ─────────────────────────────────────────────────────────
changes = []

# cell 3 교체
old3 = ''.join(nb['cells'][3]['source'])
nb['cells'][3]['source'] = CELL3
changes.append(f'cell[3] (0-2 데이터현황): {len(old3)} -> {len(CELL3)} chars')

# cell 15 교체
old15 = ''.join(nb['cells'][15]['source'])
nb['cells'][15]['source'] = CELL15
changes.append(f'cell[15] (3-4 거시경제): {len(old15)} -> {len(CELL15)} chars')

# cell 14 (part3-md) 패치
src14 = ''.join(nb['cells'][14]['source'])
new14 = src14.replace(CELL14_PATCH['old'], CELL14_PATCH['new'])
new14 = new14.replace(CELL14_PATCH2['old'], CELL14_PATCH2['new'])
if new14 != src14:
    nb['cells'][14]['source'] = new14
    changes.append(f'cell[14] (part3-md): 유가 수치 업데이트')
else:
    changes.append(f'cell[14] (part3-md): 변경 없음 (이미 최신)')

with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print('=== 노트북 업데이트 완료 ===')
for c in changes:
    print(f'  {c}')
print(f'최종 셀 수: {len(nb["cells"])}')
