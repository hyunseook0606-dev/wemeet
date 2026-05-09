"""
노트북 재구성 스크립트
=======================
wemeet_v4_main.ipynb에서 Part 4, Part 5, Part 7을 제거하고
새로운 Part 4(MRI 유사사례), Part 5(ODCY 추천), Part 6(루티 JSON)을 추가합니다.

실행: python scripts/rebuild_notebook.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
NB_PATH = ROOT / "notebooks" / "wemeet_v4_main.ipynb"
OUT_PATH = ROOT / "notebooks" / "wemeet_v4_main.ipynb"   # 동일 파일 덮어쓰기


# ──────────────────────────────────────────────────────────
# 헬퍼: 마크다운 셀 생성
# ──────────────────────────────────────────────────────────

def md_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source,
    }


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


# ──────────────────────────────────────────────────────────
# 새로운 Part 4 — MRI 과거 유사사례 매칭
# ──────────────────────────────────────────────────────────

NEW_PART4_MD = """\
---
# Part 4 — MRI 과거 유사사례 매칭 시스템

## 설계 철학

MRI 수치 하나로 "기상악화 시나리오" 같은 라벨을 붙이면 오류가 발생합니다.
예) MRI 0.55는 전쟁 상황일 수도, 태풍일 수도 있습니다.

> **대신 이렇게 합니다:**
> 현재 MRI 수치와 가장 유사했던 과거 실제 사례를 찾아
> *"이전에 이 정도 수치가 나왔을 때, 이런 일이 있었어요"* 형식으로 고객에게 제공합니다.

```
현재 MRI → 과거 유사사례 DB 매칭 → 상위 3개 사례 제시
         → 고객: "이때 평균 지연 X일, 운임 +Y% 였군요"
         → 포워더에게 더 똑똑한 지시 가능
```

### 유사도 계산 방식
| 요소 | 가중치 | 설명 |
|---|---|---|
| MRI 피크 거리 | 기본 | \\|현재 MRI − 과거 사례 피크\\| |
| MRI 범위 이탈 | +0.20 | 현재 MRI가 과거 사례 발생 구간 밖일 때 |
| 리스크 카테고리 불일치 | +0.15 | NLP 분류 결과와 과거 사례 카테고리 불일치 시 |
"""

NEW_PART4_CODE = """\
from src.historical_matcher import find_similar_events, format_customer_message

# Part 2에서 산출된 MRI 값과 NLP 분류 결과 사용
# (Part 1~2가 실행된 후 mri_score, detected_categories 변수 존재 가정)
try:
    _mri = float(mri_score)
except NameError:
    _mri = 0.72   # 시뮬레이션 기본값

try:
    _cats = detected_categories   # Part 1 NLP 분류 결과
except NameError:
    _cats = ["지정학분쟁"]        # 시뮬레이션 기본값

print(f"현재 MRI: {_mri:.2f}  |  감지 카테고리: {_cats}")
print()

similar = find_similar_events(current_mri=_mri, detected_categories=_cats, top_k=3)
print(format_customer_message(_mri, similar))
"""

NEW_PART4_VIZ_MD = """\
## 4-2. 유사사례 시각화 (홈페이지 대시보드용)

과거 사례의 MRI 수치 분포와 현재 MRI를 함께 표시합니다.
"""

NEW_PART4_VIZ_CODE = """\
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle(f'MRI {_mri:.2f} 기준 — 과거 유사사례 분석', fontsize=14, fontweight='bold')

# ── 왼쪽: MRI 범위 비교 차트 ──────────────────────────────
from src.historical_matcher import HISTORICAL_EVENTS

colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db', '#9b59b6', '#1abc9c']
for i, ev in enumerate(HISTORICAL_EVENTS):
    ax1.barh(
        ev.name[:18], ev.mri_range[1] - ev.mri_range[0],
        left=ev.mri_range[0],
        color=colors[i % len(colors)], alpha=0.6, height=0.6,
    )
    ax1.scatter(ev.mri_peak, ev.name[:18], color=colors[i % len(colors)], zorder=5, s=50)

ax1.axvline(_mri, color='black', linewidth=2.5, linestyle='--', label=f'현재 MRI ({_mri:.2f})')
ax1.set_xlabel('MRI 수치')
ax1.set_title('과거 사례별 MRI 발생 구간')
ax1.legend()
ax1.set_xlim(0, 1)
ax1.grid(axis='x', alpha=0.3)

# ── 오른쪽: 상위 3개 사례 비교 막대 ─────────────────────
names    = [f"[{e['rank']}] {e['name'][:14]}" for e in similar]
delays   = [e['avg_delay_days'] for e in similar]
freights = [e['avg_freight_increase_pct'] for e in similar]

x = np.arange(len(names))
w = 0.35
ax2b = ax2.twinx()

bars1 = ax2.bar(x - w/2, delays, w, label='평균 지연(일)', color='#e74c3c', alpha=0.75)
bars2 = ax2b.bar(x + w/2, freights, w, label='운임 상승(%)', color='#3498db', alpha=0.75)

ax2.set_ylabel('평균 지연 (일)', color='#e74c3c')
ax2b.set_ylabel('운임 상승 (%)', color='#3498db')
ax2.set_xticks(x)
ax2.set_xticklabels(names, rotation=15, ha='right', fontsize=8)
ax2.set_title('유사 사례 상위 3개 — 지연·운임 비교')

lines = [mpatches.Patch(color='#e74c3c', alpha=0.75, label='평균 지연(일)'),
         mpatches.Patch(color='#3498db', alpha=0.75, label='운임 상승(%)')]
ax2.legend(handles=lines, loc='upper left')
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('data/mri_similar_events.png', dpi=150, bbox_inches='tight')
plt.show()
print('\\n✅ 저장: data/mri_similar_events.png')
"""


# ──────────────────────────────────────────────────────────
# Part 3 추가 셀 — LSTM 고객 인사이트
# ──────────────────────────────────────────────────────────

LSTM_INSIGHT_MD = """\
## 3-3. LSTM 예측 → 고객 인사이트 3종

부산항 물동량 LSTM 예측 결과를 화주가 활용할 수 있는 정보로 변환합니다.

| 인사이트 | 설명 | 화주 활용 |
|---|---|---|
| **혼잡도 예보** | 예측 물동량 vs 평년 비교 | 출항 일정 판단 |
| **최적 출항 시기** | 물동량 저점 구간 탐지 | 선적 타이밍 최적화 |
| **ODCY 수요 예보** | 물동량 급등 시 창고 수요↑ | 보관 공간 선점 |
"""

LSTM_INSIGHT_CODE = """\
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# Part 3 LSTM 결과 변수 가정: pred_future (예측값), dates_future (날짜)
# 없으면 더미 데이터로 시연
try:
    _pred   = pred_future.flatten()
    _dates  = pd.to_datetime(dates_future)
except NameError:
    np.random.seed(42)
    _base   = 2_030_000
    _noise  = np.random.normal(0, 80_000, 12)
    _trend  = np.linspace(0, 120_000, 12)
    _pred   = _base + _noise + _trend
    _dates  = pd.date_range(start='2026-06-01', periods=12, freq='ME')
    print("⚠️  LSTM 예측 결과 없음 → 시뮬레이션 데이터 사용")

BASELINE_TEU = 2_030_000   # 부산항 평년 월평균 TEU (2024 실적 기준)

df_pred = pd.DataFrame({'date': _dates, 'teu': _pred})
df_pred['vs_baseline_pct'] = (df_pred['teu'] - BASELINE_TEU) / BASELINE_TEU * 100
df_pred['congestion_risk'] = df_pred['vs_baseline_pct'].apply(
    lambda x: '🔴 혼잡 우려' if x > 10 else ('🟡 주의' if x > 3 else '🟢 양호')
)

# ── 인사이트 1: 혼잡도 예보 출력 ────────────────────────
print("━━━ 혼잡도 예보 (향후 12개월) ━━━")
print(f"{'월':<12} {'예측 TEU':>12} {'평년 대비':>10} {'상태'}")
print("─" * 45)
for _, row in df_pred.iterrows():
    print(f"{row['date'].strftime('%Y-%m'):<12} "
          f"{row['teu']:>12,.0f} "
          f"{row['vs_baseline_pct']:>+9.1f}% "
          f"  {row['congestion_risk']}")

# ── 인사이트 2: 최적 출항 시기 ──────────────────────────
min_row = df_pred.loc[df_pred['teu'].idxmin()]
print(f"\\n⭐ 최적 출항 시기: {min_row['date'].strftime('%Y년 %m월')}")
print(f"   예측 물동량: {min_row['teu']:,.0f} TEU "
      f"(평년 대비 {min_row['vs_baseline_pct']:+.1f}%)")
print(f"   → 혼잡도가 낮아 선적 지연·운임 프리미엄 가능성 낮음")

# ── 인사이트 3: ODCY 수요 예보 ──────────────────────────
high_months = df_pred[df_pred['vs_baseline_pct'] > 10]
if not high_months.empty:
    months_str = ', '.join(high_months['date'].dt.strftime('%m월').tolist())
    print(f"\\n⚠️  ODCY·창고 수요 급등 예상 구간: {months_str}")
    print(f"   → 해당 기간 ODCY 사전 예약을 권장합니다.")
else:
    print("\\n✅ 향후 12개월 내 ODCY 수요 급등 구간 없음")

# ── 시각화 ───────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13, 5))
colors_bar = ['#e74c3c' if p > 10 else ('#f39c12' if p > 3 else '#2ecc71')
              for p in df_pred['vs_baseline_pct']]
ax.bar(df_pred['date'], df_pred['teu'] / 1e4, color=colors_bar, alpha=0.8, width=20)
ax.axhline(BASELINE_TEU / 1e4, color='navy', linewidth=1.8, linestyle='--', label='평년 기준선')
ax.axvline(min_row['date'], color='gold', linewidth=2.5, linestyle=':', label=f"최적 출항 {min_row['date'].strftime('%m월')}")
ax.set_xlabel('월')
ax.set_ylabel('예측 물동량 (만 TEU)')
ax.set_title('부산항 물동량 LSTM 예측 — 혼잡도 예보 & 최적 출항 시기', fontsize=12)
ax.legend()
ax.xaxis.set_major_formatter(mdates.DateFormatter('%y/%m'))
plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')
patches = [
    plt.Rectangle((0,0),1,1, color='#e74c3c', alpha=0.8, label='🔴 혼잡 우려 (>+10%)'),
    plt.Rectangle((0,0),1,1, color='#f39c12', alpha=0.8, label='🟡 주의 (>+3%)'),
    plt.Rectangle((0,0),1,1, color='#2ecc71', alpha=0.8, label='🟢 양호'),
]
ax.legend(handles=patches + ax.get_legend_handles_labels()[0][2:], loc='upper left', fontsize=8)
plt.tight_layout()
plt.savefig('data/lstm_customer_insight.png', dpi=150, bbox_inches='tight')
plt.show()
print('\\n✅ 저장: data/lstm_customer_insight.png')
"""


# ──────────────────────────────────────────────────────────
# 새로운 Part 5 — 창고·ODCY 자동 탐색 & 추천
# ──────────────────────────────────────────────────────────

NEW_PART5_MD = """\
---
# Part 5 — 항만 주변 창고·ODCY 자동 탐색 & 추천

## 운송 시나리오 전체 흐름

```
[화주] 루티(ROOUTY)에 화물 정보 입력
       (화물 종류, 수량, 출발지, 도착지, 운송 일정)
          ↓
[위밋 플랫폼] MRI 상승 감지 → 화주에게 선제 알림
          ↓
[본 기능] 도착 항만 주변 창고·ODCY 자동 탐색
    └─ 화물 종류에 맞는 시설 필터 (냉장/냉동/위험물/배터리 등)
    └─ 3가지 추천 모드 제시
          ↓
[화주] 후보지 선택 → 포워더에게 "이 ODCY로 운송 요청"
          ↓
[루티] Phase 1 JSON으로 출발지 → 선택 창고 운송 수행
          ↓
[선적 재개 시] Phase 2 JSON으로 창고 → CY 운송 수행
```

## 추천 3가지 모드

| 모드 | 기준 | 활용 상황 |
|---|---|---|
| 📍 거리 최단 | 항만~창고 직선·도로 거리 최소 | 비용 절감이 최우선일 때 |
| ⏱ 시간 최단 | 실제 도로 소요 시간 최소 | 마감 시간이 촉박할 때 |
| ⭐ 종합 추천 | 거리+시간+시설 완성도 종합 | 일반적 상황 (기본값) |

## 화물 종류별 창고 요구사항

| 화물 | 냉동/냉장 | 위험물 인허가 | 특이사항 |
|---|---|---|---|
| 일반화물 | ✗ | ✗ | ODCY·일반창고 |
| 냉장화물 | 0~10°C | ✗ | 콜드체인 필수 |
| 냉동화물 | -25~-18°C | ✗ | 냉동 전력 확인 |
| 위험물 | ✗ | ✅ | IMDG 인허가 보세창고 |
| 자동차부품 | ✗ | ✗ | 중량물 설비 |
| **2차전지** | 15~25°C | ✅ | 화재진압 + IMDG Class 9 |
| 의류/섬유 | ✗ | ✗ | 방습·방진 권장 |
| 전자제품 | 10~30°C | ✗ | 정전기 차폐 권장 |
"""

NEW_PART5_CODE = """\
from src.odcy_recommender import (
    CargoType, recommend_storage, format_storage_message, CARGO_REQUIREMENTS
)
import os

# ── 시나리오 입력값 (루티 입력 데이터 활용) ─────────────────
# 실제 운영 시: 루티에 화주가 입력한 값을 그대로 사용
SCENARIO = {
    "port_name":   "부산항(북항)",    # 도착 항만
    "cargo_type":  CargoType.BATTERY,  # 화물 종류 (변경 가능)
    "company":     "화주_K",
    "shipment_id": "SH-011",
    "cbm":         13.9,
    "origin":      "경상북도 구미시 공단동 배터리공장",
    "pickup_date": "2026-05-11",
    "mri_now":     _mri if '_mri' in dir() else 0.72,
}

print(f"━━━ 입력 정보 ━━━")
print(f"  항만:   {SCENARIO['port_name']}")
print(f"  화물:   {SCENARIO['cargo_type'].value}")
req = CARGO_REQUIREMENTS[SCENARIO['cargo_type']]
print(f"  조건:   {req['description']}")
if req['special_notes']:
    print(f"  ⚠️   {req['special_notes']}")
print()

# ── 창고 탐색 & 추천 ─────────────────────────────────────────
# KAKAO_REST_API_KEY 환경변수가 있으면 실제 API, 없으면 시뮬레이션
result = recommend_storage(
    port_name          = SCENARIO['port_name'],
    cargo_type         = SCENARIO['cargo_type'],
    top_n              = 3,
    search_radius_m    = 15000,
    kakao_rest_key     = os.getenv("KAKAO_REST_API_KEY"),
    kakao_mobility_key = os.getenv("KAKAO_MOBILITY_KEY"),
)

print(format_storage_message(result))
"""

NEW_PART5_MAP_CODE = """\
# ── 지도 시각화 (folium 없으면 matplotlib fallback) ──────────
try:
    import folium
    from src.odcy_recommender import PORT_COORDINATES

    port_lat, port_lng = PORT_COORDINATES[SCENARIO['port_name']]
    m = folium.Map(location=[port_lat, port_lng], zoom_start=12)

    # 항만 마커
    folium.Marker(
        [port_lat, port_lng],
        popup=f"🚢 {SCENARIO['port_name']}",
        icon=folium.Icon(color='blue', icon='ship', prefix='fa'),
    ).add_to(m)

    # 추천 창고 마커
    mode_colors = {'comprehensive': 'red', 'distance': 'green', 'time': 'orange'}
    plotted_ids = set()
    for mode, color in mode_colors.items():
        for rank, wh in enumerate(result['recommendations'][mode], 1):
            wh_id = wh.get('id', wh['name'])
            if wh_id in plotted_ids:
                continue
            plotted_ids.add(wh_id)
            # 시뮬 DB는 lat/lng 있음, 카카오 결과는 추정
            sim_wh = next((w for w in __import__('src.odcy_recommender', fromlist=['SIMULATION_WAREHOUSES']).SIMULATION_WAREHOUSES
                           if w['id'] == wh_id), None)
            if sim_wh:
                folium.Marker(
                    [sim_wh['lat'], sim_wh['lng']],
                    popup=(f"<b>{wh['name']}</b><br>{wh['address']}<br>"
                           f"거리: {wh['distance_km']}km | {wh['duration_min']}분<br>"
                           f"종합추천: {'⭐' if mode=='comprehensive' and rank==1 else ''}"),
                    icon=folium.Icon(color=color, icon='warehouse', prefix='fa'),
                ).add_to(m)

    map_path = 'data/odcy_map.html'
    m.save(map_path)
    print(f"\\n🗺️  지도 저장: {map_path}")
    display(m)

except ImportError:
    # folium 없을 때 matplotlib scatter
    import matplotlib.pyplot as plt
    from src.odcy_recommender import PORT_COORDINATES, SIMULATION_WAREHOUSES

    port_lat, port_lng = PORT_COORDINATES[SCENARIO['port_name']]
    fig, ax = plt.subplots(figsize=(9, 7))

    # 항만
    ax.scatter(port_lng, port_lat, s=300, c='navy', marker='*', zorder=10, label=SCENARIO['port_name'])

    # 전체 DB 창고 (회색)
    for wh in SIMULATION_WAREHOUSES:
        ax.scatter(wh['lng'], wh['lat'], s=60, c='lightgray', edgecolors='gray', zorder=5)
        ax.annotate(wh['name'][:10], (wh['lng'], wh['lat']), fontsize=6, ha='center', va='bottom')

    # 종합 추천 상위 3개 (강조)
    colors_rank = ['#e74c3c', '#f39c12', '#27ae60']
    for rank, wh_info in enumerate(result['recommendations']['comprehensive'], 1):
        sim_wh = next((w for w in SIMULATION_WAREHOUSES if w['id'] == wh_info.get('id', '')), None)
        if sim_wh:
            ax.scatter(sim_wh['lng'], sim_wh['lat'], s=200,
                       c=colors_rank[rank-1], edgecolors='black', zorder=9,
                       label=f"⭐ 종합추천 {rank}위: {sim_wh['name'][:14]}")
            ax.plot([port_lng, sim_wh['lng']], [port_lat, sim_wh['lat']],
                    '--', color=colors_rank[rank-1], alpha=0.6, linewidth=1.5)

    ax.set_xlabel('경도')
    ax.set_ylabel('위도')
    ax.set_title(f"{SCENARIO['port_name']} 주변 창고·ODCY 추천 ({SCENARIO['cargo_type'].value})", fontsize=12)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('data/odcy_map.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("\\n✅ 저장: data/odcy_map.png (folium 미설치 → matplotlib 대체)")
"""


# ──────────────────────────────────────────────────────────
# 새로운 Part 6 — 루티 연계 JSON (창고 운송용으로 재구성)
# ──────────────────────────────────────────────────────────

NEW_PART6_MD = """\
---
# Part 6 — 루티 연계 JSON 출력 (창고 운송 Phase 1 & 2)

## 왜 2단계 JSON인가?

해상 리스크 대응은 **두 번의 운송**이 필요합니다:

```
Phase 1: 출발지 → 항만 인근 창고·ODCY   (지연 발생 즉시)
Phase 2: 창고·ODCY → 항만 CY            (선적 재개 시)
```

위밋 플랫폼이 Phase 1 JSON을 생성하면, 루티가 즉시 배차 최적화를 수행합니다.
Phase 2는 선적 재개 일정이 확정되는 시점에 자동 생성됩니다.

```
[위밋 플랫폼] → Phase 1 JSON → [루티 API] → 창고 운송 배차
                → Phase 2 JSON → [루티 API] → CY 반입 배차
```

> **현재**: `integration_status = 'simulation_mode'`
> **연동 시**: `POST /v1/dispatch/execute` 엔드포인트로 전송
"""

NEW_PART6_CODE = """\
from src.storage_routy_adapter import (
    generate_storage_routy_json, generate_phase2_routy_json, save_storage_json
)
from pathlib import Path
import json

ROUTY_DIR = Path('routy_inputs')

# 종합 추천 1위 창고 선택
top_warehouse = result['recommendations']['comprehensive'][0]

# ── Phase 1: 출발지 → 창고 ──────────────────────────────────
phase1 = generate_storage_routy_json(
    shipment_id       = SCENARIO['shipment_id'],
    company           = SCENARIO['company'],
    region            = "경상북부",
    cargo_type        = SCENARIO['cargo_type'].value,
    cbm               = SCENARIO['cbm'],
    cold_chain        = CARGO_REQUIREMENTS[SCENARIO['cargo_type']]['cold_chain'],
    hazmat            = CARGO_REQUIREMENTS[SCENARIO['cargo_type']]['hazmat'],
    origin_address    = SCENARIO['origin'],
    original_port     = SCENARIO['port_name'],
    original_pickup_date = SCENARIO['pickup_date'],
    mri_current       = SCENARIO['mri_now'],
    delay_reason      = "해상 리스크 상승 (MRI 기반 HOLDBACK 결정)",
    recommended_warehouse = top_warehouse,
    phase2_ready_date = "2026-05-25",   # 선적 재개 예정일 (예시)
)

# ── Phase 2: 창고 → CY ──────────────────────────────────────
phase2 = generate_phase2_routy_json(
    phase1_json    = phase1,
    cy_address     = "부산광역시 동구 초량동 부산항 1부두 CY",
    cy_closing_date = "2026-05-23",    # CY Cut (출항 3일 전)
)

# ── 출력 & 저장 ─────────────────────────────────────────────
for phase_name, data in [("Phase 1 (출발지→창고)", phase1), ("Phase 2 (창고→CY)", phase2)]:
    print(f"\\n{'='*60}")
    print(f"루티 JSON — {phase_name}")
    print('='*60)
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    fp = save_storage_json(data, ROUTY_DIR)
    print(f"\\n✅ 저장: {fp.name}")
"""


# ──────────────────────────────────────────────────────────
# 노트북 재구성 메인 함수
# ──────────────────────────────────────────────────────────

def rebuild():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb["cells"]

    # ── Part 4 시작 셀 인덱스 탐색 ──────────────────────────
    part4_start = None
    part6_start = None
    part7_start = None

    for i, cell in enumerate(cells):
        src = "".join(cell.get("source", []))
        if "# Part 4" in src and "시나리오 자동 분류" in src:
            part4_start = i
        if "# Part 6" in src and "루티 연계 JSON" in src:
            part6_start = i
        if "# Part 7" in src and "통합 시연" in src:
            part7_start = i

    if part4_start is None:
        print("❌ Part 4 시작 셀을 찾을 수 없습니다. 노트북 구조를 확인하세요.")
        sys.exit(1)

    print(f"Part 4 시작: 셀 {part4_start}")
    print(f"Part 6 시작: 셀 {part6_start}")
    print(f"Part 7 시작: 셀 {part7_start}")

    # ── Part 3에 LSTM 인사이트 셀 추가 ──────────────────────
    lstm_cells = [
        md_cell(LSTM_INSIGHT_MD),
        code_cell(LSTM_INSIGHT_CODE),
    ]

    # ── 새 Part 4 셀 구성 ────────────────────────────────────
    new_part4_cells = [
        md_cell(NEW_PART4_MD),
        code_cell(NEW_PART4_CODE),
        md_cell(NEW_PART4_VIZ_MD),
        code_cell(NEW_PART4_VIZ_CODE),
    ]

    # ── 새 Part 5 셀 구성 ────────────────────────────────────
    new_part5_cells = [
        md_cell(NEW_PART5_MD),
        code_cell(NEW_PART5_CODE),
        code_cell(NEW_PART5_MAP_CODE),
    ]

    # ── 새 Part 6 셀 구성 ────────────────────────────────────
    new_part6_cells = [
        md_cell(NEW_PART6_MD),
        code_cell(NEW_PART6_CODE),
    ]

    # ── 셀 배열 재구성 ───────────────────────────────────────
    # 1) Part 0~3 유지 (Part 4 시작 전까지)
    kept_cells = cells[:part4_start]

    # 2) LSTM 인사이트 삽입 (Part 3 바로 뒤)
    kept_cells += lstm_cells

    # 3) 새 Part 4, 5, 6 추가
    kept_cells += new_part4_cells
    kept_cells += new_part5_cells
    kept_cells += new_part6_cells

    nb["cells"] = kept_cells

    # ── 목차 셀 업데이트 ─────────────────────────────────────
    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell.get("source", []))
        if "Part 4" in src and "시나리오 자동 분류" in src:
            new_src = src.replace(
                "| **Part 4** | 시나리오 자동 분류 | 5개 시나리오, 정책 분기 |",
                "| **Part 4** | MRI 유사사례 매칭 | 과거 사례 DB, 고객 정보 제공 |",
            ).replace(
                "| **Part 5** | 운영 재조정 엔진 | 우선처리·보류·이동·통합 |",
                "| **Part 5** | 창고·ODCY 자동 추천 | 카카오 API, 3모드 추천 |",
            ).replace(
                "| **Part 6** | 루티 연계 JSON 출력 | 표준 API 입력 형식 |",
                "| **Part 6** | 루티 JSON (창고 운송) | Phase 1·2 JSON, 시나리오 |",
            ).replace(
                "| **Part 7** | 통합 시연 (발표용) | 5개 시나리오 비교, 케이스 스터디 |",
                "",
            )
            if isinstance(cell["source"], list):
                cell["source"] = [new_src]
            else:
                cell["source"] = new_src
            break

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print(f"\n✅ 노트북 재구성 완료: {OUT_PATH}")
    print(f"   총 셀 수: {len(nb['cells'])} (기존 {len(cells)}에서 변경)")


if __name__ == "__main__":
    rebuild()
