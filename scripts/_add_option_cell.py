"""노트북에 4가지 옵션 비교 셀 삽입."""
import json
from pathlib import Path

NB_PATH = Path(__file__).parent.parent / 'notebooks' / 'wemeet_v4_main.ipynb'

CELL_SRC = """\
# ── 4가지 대응 옵션 비교 (핵심 차별화 기능) ──────────────────────
# MRI 고위험 시 화주에게 A/B/C/D 4안을 제시하고 비용을 비교합니다.
# 강요 없음 — 화주가 직접 선택. 플랫폼은 추천 + 비용 산출만 제공.
from src.option_presenter import generate_four_options, format_option_table, format_option_detail
import matplotlib.pyplot as plt
import numpy as np

# ── 시나리오 연동 (이전 셀 변수 활용) ────────────────────────────
try:
    _shipment_in = SCENARIO            # cell[23] SCENARIO dict
    _delay       = 14                  # B_GEOPOLITICAL 기준 14일
    _freight     = int(_shipment_in['cbm'] * 45)
except NameError:
    _shipment_in = {'cargo_type': '일반화물', 'cbm': 15.0, 'region': '경기남부'}
    _delay, _freight = 14, 675

try:
    _storage = result                  # cell[23] recommend_storage() 결과
except NameError:
    from src.odcy_recommender import recommend_storage, CargoType
    _storage = recommend_storage('부산항(북항)', CargoType.GENERAL, top_n=3)

# ── 4가지 옵션 생성 ──────────────────────────────────────────────
options = generate_four_options(
    shipment       = _shipment_in,
    storage_result = _storage,
    delay_days     = _delay,
    freight_usd    = _freight,
)

# ── 텍스트 비교표 출력 ────────────────────────────────────────────
print(format_option_table(options))

# ── 시각화 ────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

labels    = [f'{o.option_id}안' for o in options]
stacks    = [
    ([o.freight_usd          for o in options], '해상 운임',  '#A9D18E'),
    ([o.routy_phase1_usd     for o in options], '루티 P1',    '#2E75B6'),
    ([o.routy_phase2_usd     for o in options], '루티 P2',    '#70AD47'),
    ([o.warehouse_rental_usd for o in options], '창고 대여',  '#ED7D31'),
    ([o.warehouse_contract_usd for o in options], '계약비',   '#FFC000'),
    ([o.risk_penalty_usd     for o in options], '리스크 부담','#FF4444'),
]
x, wid = range(len(labels)), 0.5
bottoms = [0.0] * len(options)
for vals, lbl, col in stacks:
    ax1.bar(x, vals, wid, bottom=bottoms, label=lbl, color=col, alpha=0.9)
    bottoms = [b + v for b, v in zip(bottoms, vals)]

for i, opt in enumerate(options):
    ax1.text(i, opt.total_usd + 10, f'${opt.total_usd:,.0f}',
             ha='center', fontsize=9, fontweight='bold')
ax1.set_xticks(list(x))
ax1.set_xticklabels(labels)
ax1.set_ylabel('비용 (USD)')
ax1.set_title('옵션별 비용 구성', fontweight='bold')
ax1.legend(loc='upper right', fontsize=8)
ax1.grid(axis='y', alpha=0.3)

baseline = options[0]
savings  = [opt.savings_vs(baseline) for opt in options]
bar_cols = ['#9E9E9E' if i == 0 else ('#D32F2F' if s < 0 else '#2E75B6')
            for i, s in enumerate(savings)]
ax2.bar(labels, savings, color=bar_cols, edgecolor='black', linewidth=0.5)
ax2.axhline(0, color='black', linewidth=1)
for i, (s, opt) in enumerate(zip(savings, options)):
    label = '기준' if i == 0 else (
        f'{"+" if s<0 else "-"}${abs(s):,.0f}\n({abs(opt.savings_pct_vs(baseline)):.1f}%)')
    ax2.text(i, s + (12 if s >= 0 else -30), label, ha='center', fontsize=9, fontweight='bold')
ax2.set_ylabel('A안 대비 절약액 (USD)')
ax2.set_title('A안(직송) 대비 절약 효과', fontweight='bold')
ax2.grid(axis='y', alpha=0.3)

cbm_val = _shipment_in.get('cbm', 15)
plt.suptitle(
    f'해상 리스크 대응 옵션 비교  |  지연 예상 {_delay}일  |  화물 {cbm_val:.1f}CBM',
    fontsize=12, fontweight='bold'
)
plt.tight_layout()
plt.savefig(ROOT / 'data' / 'option_comparison.png', dpi=150, bbox_inches='tight')
plt.show()
print('\\n✅ 저장: data/option_comparison.png')

# ── D안 선택 시 상세 안내 ─────────────────────────────────────────
print()
opt_d = next((o for o in options if o.option_id == 'D'), options[-1])
print(format_option_detail(opt_d, baseline))
"""

with open(NB_PATH, encoding='utf-8') as f:
    nb = json.load(f)

# 이미 삽입됐으면 건너뜀
for cell in nb['cells']:
    if 'option_presenter' in ''.join(cell['source']):
        print('이미 존재, 업데이트')
        cell['source'] = [CELL_SRC]
        cell['outputs'] = []
        cell['execution_count'] = None
        with open(NB_PATH, 'w', encoding='utf-8') as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
        print('업데이트 완료')
        break
else:
    # cell[23] 다음에 새 셀 삽입
    new_cell = {
        'cell_type': 'code',
        'execution_count': None,
        'metadata': {},
        'outputs': [],
        'source': [CELL_SRC],
    }
    nb['cells'].insert(24, new_cell)
    with open(NB_PATH, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print(f'삽입 완료: 총 {len(nb["cells"])}개 셀')
