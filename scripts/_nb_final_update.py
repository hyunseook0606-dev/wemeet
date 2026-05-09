# -*- coding: utf-8 -*-
"""노트북 최종 통합 업데이트: 데이터현황/NLIC삭제/MRI/LSTM/거시경제"""
import json
from pathlib import Path

NB = Path('notebooks/wemeet_v4_main.ipynb')
with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

changes = []

# ══════════════════════════════════════════════════════════════════
# 1) cell[3] — 0-2 데이터현황: BPA API + Excel 설명 추가
# ══════════════════════════════════════════════════════════════════
CELL3 = (
    "# 0-2. 데이터 소스 전체 현황\n"
    "from src.real_data_fetcher import print_data_status\n"
    "print_data_status()\n"
    "\n"
    "print('\\n[운임지수 (KCCI)]')\n"
    "kcci_csv = DATA_DIR / 'kcci_weekly.csv'\n"
    "xls_files = list((DATA_DIR/'freight_index').glob('*.xls')) + list((DATA_DIR/'freight_index').glob('*.xlsx'))\n"
    "if kcci_csv.exists():\n"
    "    import pandas as _pd\n"
    "    _k = _pd.read_csv(kcci_csv, encoding='utf-8-sig')\n"
    "    print(f'  kcci_weekly.csv: {len(_k)}주 (XLS 합치기 완료)')\n"
    "elif xls_files:\n"
    "    print(f'  XLS {len(xls_files)}개 확인 → --combine-freight 실행 필요')\n"
    "else:\n"
    "    print('  없음 → data/freight_index/ 에 XLS 저장 후 --combine-freight 실행')\n"
    "\n"
    "print('\\n[부산항 컨테이너 물동량]')\n"
    "print('  2020~2024: BPA 공공데이터포털 API (데이터셋 15055478)')\n"
    "print('             → 연도별 TEU + 계절 분해 → 월별 추정치')\n"
    "print('  2025:      수동 수집 Excel (BPA 홈페이지 업데이트 자료)')\n"
    "print('             → 260414_홈페이지 업데이트_전국항 및 부산항 컨테이너 물동량')\n"
    "print('             → 2025년 연간 합계 24,882,355 TEU → 월평균 207.4만 TEU')\n"
    "from src.data_loader import load_busan_throughput_combined\n"
    "_tp = load_busan_throughput_combined(DATA_DIR, start_year=2020)\n"
    "if _tp is not None:\n"
    "    print(f'  로드 완료: {len(_tp)}개월 ({_tp[\"date\"].iloc[0].strftime(\"%Y.%m\")} ~ {_tp[\"date\"].iloc[-1].strftime(\"%Y.%m\")})')\n"
    "else:\n"
    "    print('  로드 실패 → 시뮬 폴백')\n"
    "\n"
    "import json as _json\n"
    "rates_fp = DATA_DIR / 'today_rates.json'\n"
    "if rates_fp.exists():\n"
    "    _rates = _json.loads(rates_fp.read_text(encoding='utf-8'))\n"
    "    _today_key = sorted(_rates.keys())[-1]\n"
    "    _d = _rates[_today_key]\n"
    "    print(f'\\n[오늘 자동수집 실데이터] ({_today_key})')\n"
    "    if 'usd_krw' in _d: print(f'  환율: {_d[\"usd_krw\"]:,.0f}원/달러  [frankfurter.app]')\n"
    "    if 'brent_usd' in _d: print(f'  유가: ${_d[\"brent_usd\"]:.2f}/배럴 (Brent)  [Yahoo Finance]')\n"
    "\n"
    "print('\\n[자동 갱신 스케줄]')\n"
    "print('  매일  08:30   환율 (frankfurter.app) + 유가 (Yahoo Finance BZ=F)')\n"
    "print('  매주 월 09:00  운임지수 (XLS 폴더 감시 + 합치기)')\n"
    "print('  등록: .\\\\scripts\\\\setup_scheduler.ps1')\n"
)
nb['cells'][3]['source'] = CELL3
changes.append('cell[3]: 데이터현황 — BPA API+Excel 설명 추가')

# ══════════════════════════════════════════════════════════════════
# 2) cell[4] — 0-3 NLIC 삭제 → 빈 마크다운으로 대체 후 제거
# ══════════════════════════════════════════════════════════════════
cell4_src = ''.join(nb['cells'][4]['source'])
if 'NLIC' in cell4_src or 'nlic' in cell4_src.lower():
    nb['cells'].pop(4)
    changes.append('cell[4]: 0-3 NLIC 셀 삭제')

# ══════════════════════════════════════════════════════════════════
# 3) cell[14 or 15] — 3-4 거시경제: load_busan_throughput_combined 사용
# ══════════════════════════════════════════════════════════════════
# 삭제 후 인덱스 재계산
macro_idx = None
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell['source'])
    if '3-4. 거시경제' in src and 'fetch_bpa_throughput' in src:
        macro_idx = i
        break

if macro_idx is not None:
    CELL_MACRO = (
        "# 3-4. 거시경제 데이터 수집\n"
        "# [물동량] BPA API(2020~2024) + Excel(2025) 결합 → 총 72개월\n"
        "# [환율]   frankfurter.app 일별 자동수집\n"
        "# [유가]   Yahoo Finance BZ=F 일별 자동수집\n"
        "from src.data_loader import load_busan_throughput_combined, load_oil_price\n"
        "from src.real_data_fetcher import (\n"
        "    fetch_ecos_exchange_rate, fetch_exchange_rate_monthly,\n"
        "    fetch_ecos_oil_price,\n"
        ")\n"
        "from src.lstm_forecaster import build_main_df\n"
        "import json as _json\n"
        "\n"
        "# ── 물동량: BPA API(2020~2024) + Excel(2025) ─────────────────\n"
        "throughput_df = load_busan_throughput_combined(DATA_DIR, start_year=2020)\n"
        "if throughput_df is not None:\n"
        "    throughput_src = 'BPA API(2020~2024) + Excel(2025) → 계절분해'\n"
        "else:\n"
        "    throughput_src = '시뮬'\n"
        "\n"
        "# ── 환율: ECOS → frankfurter.app ────────────────────────────\n"
        "fx_ecos = fetch_ecos_exchange_rate('202001', cache_dir=CACHE_DIR)\n"
        "if fx_ecos is not None:\n"
        "    fx_df, fx_src = fx_ecos, 'ECOS 한국은행 (공식)'\n"
        "else:\n"
        "    fx_df = fetch_exchange_rate_monthly(start='2020-01-01')\n"
        "    fx_src = 'frankfurter.app (일별 자동수집)' if fx_df is not None else '시뮬'\n"
        "\n"
        "# ── 유가: Yahoo Finance 캐시 → 라이브 ──────────────────────\n"
        "oil_df = load_oil_price(DATA_DIR, use_real=True)\n"
        "if oil_df is not None:\n"
        "    oil_src = 'Yahoo Finance Brent (일별 자동수집)'\n"
        "else:\n"
        "    oil_ecos = fetch_ecos_oil_price('202001', cache_dir=CACHE_DIR)\n"
        "    oil_df, oil_src = (oil_ecos, 'ECOS 두바이유') if oil_ecos is not None else (None, '시뮬')\n"
        "\n"
        "# ── 통합 DataFrame ──────────────────────────────────────────\n"
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
        "    print(f'         (오늘 실시간: ${_today_oil:.2f}/배럴)')\n"
        "print()\n"
        "print(f'[최신 실제값 ({latest_ym})]')\n"
        "print(f'  물동량: {latest[\"throughput\"]:.1f}만 TEU')\n"
        "print(f'  환율:   {latest[\"exchange_rate\"]:.0f}원/달러')\n"
        "print(f'  유가:   ${latest[\"oil_price\"]:.1f}/배럴')\n"
        "print(f'  MRI:    {latest[\"mri\"]:.4f}')\n"
        "print()\n"
        "print('[최근 6개월 추이 — LSTM 입력값]')\n"
        "recent = main_df.tail(6)[['date','throughput','exchange_rate','oil_price']].copy()\n"
        "recent['date'] = recent['date'].dt.strftime('%Y.%m')\n"
        "recent.columns = ['월','물동량(만TEU)','환율(원)','유가($)']\n"
        "print(recent.to_string(index=False))\n"
        "main_df.tail(3)\n"
    )
    nb['cells'][macro_idx]['source'] = CELL_MACRO
    changes.append(f'cell[{macro_idx}]: 거시경제 — load_busan_throughput_combined 사용')

# ══════════════════════════════════════════════════════════════════
# 4) cell[13] — MRI 시각화: 호르무즈 봉쇄 + 관세 분리
# ══════════════════════════════════════════════════════════════════
mri_vis_idx = None
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell['source'])
    if '2-4. MRI 시계열 시각화' in src:
        mri_vis_idx = i
        break

if mri_vis_idx is not None:
    CELL_MRI = (
        "# ──────────────────────────────────────────────────────────\n"
        "# 2-4. MRI 시계열 시각화\n"
        "# ──────────────────────────────────────────────────────────\n"
        "fig, axes = plt.subplots(2, 1, figsize=(13, 7))\n"
        "\n"
        "# 상단: MRI 전체 추이\n"
        "ax = axes[0]\n"
        "ax.plot(mri_df['date'], mri_df['mri'], color='#1F4E79', linewidth=2, label='MRI')\n"
        "ax.fill_between(mri_df['date'], 0, mri_df['mri'], alpha=0.15, color='#1F4E79')\n"
        "ax.axhline(0.8, color='#EF5350', linestyle='--', alpha=0.7, label='위험(0.8)')\n"
        "ax.axhline(0.6, color='#FF7043', linestyle='--', alpha=0.7, label='경계(0.6)')\n"
        "ax.axhline(0.3, color='#FFA726', linestyle='--', alpha=0.7, label='주의(0.3)')\n"
        "ax.axhline(today_mri, color='#1565C0', linewidth=2.5, label=f'오늘 MRI={today_mri:.3f}')\n"
        "\n"
        "# 주요 이벤트 표시 (3가지 구분)\n"
        "ax.axvspan(pd.Timestamp('2023-12-01'), pd.Timestamp('2024-06-01'),\n"
        "           alpha=0.12, color='red', label='홍해 사태(2023.12~2024.06)')\n"
        "ax.axvspan(pd.Timestamp('2025-04-01'), pd.Timestamp('2025-06-01'),\n"
        "           alpha=0.12, color='orange', label='미중 관세 충격(2025.04~06)')\n"
        "ax.axvspan(pd.Timestamp('2025-06-01'), mri_df['date'].max(),\n"
        "           alpha=0.12, color='darkred', label='호르무즈 봉쇄(2025.06~)')\n"
        "\n"
        "# 이벤트 텍스트 어노테이션\n"
        "ax.annotate('미중\\n관세', xy=(pd.Timestamp('2025-05-01'), 0.88),\n"
        "            fontsize=8, ha='center', color='darkorange', fontweight='bold')\n"
        "ax.annotate('호르무즈\\n봉쇄', xy=(pd.Timestamp('2025-10-01'), 0.92),\n"
        "            fontsize=8, ha='center', color='darkred', fontweight='bold')\n"
        "\n"
        "ax.set_title('Maritime Risk Index (MRI) 시계열 — AHP 기반 (2020~2026)', fontsize=12, fontweight='bold')\n"
        "ax.set_ylabel('MRI 점수 [0~1]')\n"
        "ax.set_ylim(0, 1)\n"
        "ax.legend(loc='upper left', fontsize=8, ncol=2)\n"
        "ax.grid(alpha=0.3)\n"
        "\n"
        "# 하단: 4대 하위 지수 기여도\n"
        "ax2 = axes[1]\n"
        "factors_kr = ['G\\n지정학·항로', 'N\\n자연재해·기상', 'F\\n운임 시장', 'P\\n항만·통상']\n"
        "raw_vals   = [sub_idx['G'], sub_idx['N'], sub_idx['F'], sub_idx['P']]\n"
        "wgts       = [0.483, 0.272, 0.157, 0.088]\n"
        "contribs   = [r*w for r, w in zip(raw_vals, wgts)]\n"
        "cols_sub   = ['#D32F2F', '#F57C00', '#2E75B6', '#7B7B7B']\n"
        "\n"
        "bars = ax2.bar(factors_kr, contribs, color=cols_sub, edgecolor='black')\n"
        "for bar, rv, w, c in zip(bars, raw_vals, wgts, contribs):\n"
        "    ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.002,\n"
        "             f'{rv:.2f}x{w:.3f}\\n= {c:.4f}', ha='center', fontsize=8)\n"
        "ax2.set_title(f'오늘({datetime.today().strftime(\"%Y-%m-%d\")}) MRI 하위 지수 기여도', fontsize=11, fontweight='bold')\n"
        "ax2.set_ylabel('기여도 (원점수 x 가중치)')\n"
        "ax2.grid(axis='y', alpha=0.3)\n"
        "\n"
        "plt.tight_layout()\n"
        "plt.show()\n"
        "print(f'MRI = 합계 {sum(contribs):.4f}')\n"
    )
    nb['cells'][mri_vis_idx]['source'] = CELL_MRI
    changes.append(f'cell[{mri_vis_idx}]: MRI 시각화 — 호르무즈봉쇄+관세충격 분리')

# ══════════════════════════════════════════════════════════════════
# 5) LSTM 셀 — epochs/lr/batch_size 업데이트
# ══════════════════════════════════════════════════════════════════
lstm_idx = None
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell['source'])
    if '3-5. LSTM' in src and 'train_and_forecast' in src:
        lstm_idx = i
        break

if lstm_idx is not None:
    src = ''.join(nb['cells'][lstm_idx]['source'])
    new_src = src.replace(
        'lstm_result = train_and_forecast(main_df, epochs=50)',
        'lstm_result = train_and_forecast(main_df, epochs=120, lr=0.001, batch_size=8)'
    )
    if new_src != src:
        nb['cells'][lstm_idx]['source'] = new_src
        changes.append(f'cell[{lstm_idx}]: LSTM epochs=120, lr=0.001, batch=8')

with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print('=== 노트북 업데이트 완료 ===')
for c in changes:
    print(f'  {c}')
print(f'최종 셀 수: {len(nb["cells"])}')
