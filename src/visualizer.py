"""
visualizer.py — KPI 시각화 모듈 (matplotlib + plotly)
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

from src.config import SCENARIOS


# ── 한글 폰트 자동 설정 ───────────────────────────────────────────────────────

def setup_kr_font() -> str | None:
    candidates = ['Malgun Gothic', 'AppleGothic', 'NanumGothic', 'NanumBarunGothic']
    available  = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            plt.rcParams['font.family'] = c
            plt.rcParams['axes.unicode_minus'] = False
            return c
    plt.rcParams['axes.unicode_minus'] = False
    return None

# 모듈 로드 시 즉시 적용 (노트북·스크립트 어디서 import 해도 한글 깨짐 방지)
# fm._rebuild()는 최초 import 시 폰트 캐시 강제 갱신 → Jupyter에서 □ 방지
try:
    fm._rebuild()
except Exception:
    pass
setup_kr_font()

# X축 라벨: matplotlib은 이모지(🟢🔴) 렌더링 불가 → 한글 약칭 사용
_SCENARIO_LABEL = {
    'A_NORMAL':       'A\n평상시',
    'B_GEOPOLITICAL': 'B\n지정학분쟁',
    'C_WEATHER':      'C\n기상악화',
    'D_DELAY':        'D\n단순지연',
    'E_CANCELLATION': 'E\n주문취소',
}


# ── MRI 시계열 ────────────────────────────────────────────────────────────────

def plot_mri_series(mri_df: pd.DataFrame, today_mri: float | None = None) -> None:
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(mri_df['date'], mri_df['mri'], color='#1F4E79', linewidth=2)
    ax.fill_between(mri_df['date'], 0, mri_df['mri'], alpha=0.3, color='#1F4E79')
    ax.axhline(0.55, color='#EF5350', linestyle='--', alpha=0.5, label='위험(0.55)')
    ax.axhline(0.43, color='#FF7043', linestyle='--', alpha=0.5, label='경계(0.43)')
    ax.axhline(0.33, color='#FFA726', linestyle='--', alpha=0.5, label='주의(0.33)')
    if today_mri is not None:
        ax.axhline(today_mri, color='#1565C0', linewidth=2,
                   linestyle='-', label=f'오늘 MRI={today_mri:.3f}')
    ax.set_title('Maritime Risk Index (MRI) 시계열', fontsize=13, fontweight='bold')
    ax.set_ylabel('MRI 점수')
    ax.set_ylim(0, 1)
    ax.legend(loc='upper left')
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()


# ── LSTM 학습 곡선 ────────────────────────────────────────────────────────────

def plot_lstm_loss(train_losses: list[float], val_losses: list[float]) -> None:
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(train_losses, label='Train Loss', color='#1F4E79')
    ax.plot(val_losses,   label='Val Loss',   color='#D32F2F')
    ax.set_title('LSTM 학습 곡선')
    ax.set_xlabel('Epoch')
    ax.set_ylabel('MSE Loss')
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()


# ── 시나리오별 KPI 대시보드 ───────────────────────────────────────────────────

def plot_scenario_kpi(results: dict) -> None:
    """
    5개 시나리오 일괄 실행 결과 → 4-panel KPI 시각화.
    results: run_all_scenarios() 반환값
    """
    scenario_ids = list(SCENARIOS.keys())
    labels  = [_SCENARIO_LABEL.get(sid, sid) for sid in scenario_ids]
    colors  = [SCENARIOS[sid]['color'] for sid in scenario_ids]

    def _get(sid: str, key: str) -> int:
        return results[sid]['routy_input']['summary'][key]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.patch.set_facecolor('white')
    plt.rcParams['font.size'] = 11

    # (1) 영향 받는 건수
    ax = axes[0, 0]
    vals = [_get(sid, 'affected') for sid in scenario_ids]
    bars = ax.bar(labels, vals, color=colors, edgecolor='black')
    ax.set_title('시나리오별 영향 받는 출하 건수', fontsize=12, fontweight='bold')
    ax.set_ylabel('건수')
    ax.grid(axis='y', alpha=0.3)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                str(v), ha='center', fontweight='bold')

    # (2) 행동 분류 stacked bar
    ax = axes[0, 1]
    prio = [_get(sid, 'priority') for sid in scenario_ids]
    hold = [_get(sid, 'holdback') for sid in scenario_ids]
    shft = [_get(sid, 'shifted')  for sid in scenario_ids]
    ax.bar(labels, prio, label='우선처리', color='#D32F2F', edgecolor='black')
    ax.bar(labels, hold, bottom=prio, label='반입보류', color='#F57C00', edgecolor='black')
    ax.bar(labels, shft, bottom=[p+h for p, h in zip(prio, hold)],
           label='집화이동', color='#2E75B6', edgecolor='black')
    ax.set_title('시나리오별 행동 분류', fontsize=12, fontweight='bold')
    ax.set_ylabel('건수')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # (3) 비용 변화
    ax = axes[1, 0]
    cost_deltas = [_get(sid, 'total_cost_delta_usd') for sid in scenario_ids]
    bar_colors  = ['#4CAF50' if c < 0 else ('#FFA726' if c == 0 else '#D32F2F')
                   for c in cost_deltas]
    bars = ax.bar(labels, cost_deltas, color=bar_colors, edgecolor='black')
    ax.axhline(0, color='black', linewidth=0.8)
    ax.set_title('시나리오별 운임 비용 변화', fontsize=12, fontweight='bold')
    ax.set_ylabel('USD')
    ax.grid(axis='y', alpha=0.3)
    for bar, v in zip(bars, cost_deltas):
        offset = 50 if v >= 0 else -50
        va = 'bottom' if v >= 0 else 'top'
        ax.text(bar.get_x() + bar.get_width() / 2, v + offset,
                f'${v:+,}', ha='center', va=va, fontweight='bold', fontsize=9)

    # (4) 납기 위반
    ax = axes[1, 1]
    violations = [_get(sid, 'deadline_violations') for sid in scenario_ids]
    bars = ax.bar(labels, violations, color=colors, edgecolor='black')
    ax.set_title('시나리오별 납기 위반 위험 건수', fontsize=12, fontweight='bold')
    ax.set_ylabel('건수')
    ax.grid(axis='y', alpha=0.3)
    for bar, v in zip(bars, violations):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                    str(v), ha='center', fontweight='bold', color='red')

    plt.suptitle('해상 리스크 시나리오 대응 KPI 대시보드',
                 fontsize=14, fontweight='bold', y=1.00)
    plt.tight_layout()
    plt.show()


# ── NLP 분류 결과 요약 출력 ───────────────────────────────────────────────────

def print_nlp_summary(news_df: pd.DataFrame) -> None:
    print('=' * 55)
    print('NLP 리스크 분류 결과')
    print('=' * 55)
    for _, row in news_df.iterrows():
        w = row.get('risk_weight', 0)
        icon = '🔴' if w >= 0.55 else ('🟠' if w >= 0.43 else ('🟡' if w >= 0.33 else '🟢'))
        title = row.get('title', '')[:35]
        cat   = row.get('pred_category', '')
        print(f'  {icon} [{cat:6s}] {title}')
    print(f'\n카테고리 분포:\n{news_df["pred_category"].value_counts().to_string()}')


# ── 5개 시나리오 비교 표 ──────────────────────────────────────────────────────

def print_scenario_comparison(results: dict) -> None:
    from src.config import SUB_SCENARIOS
    print('=' * 90)
    print('                   5개 시나리오 비교 (출하 30건 기준)')
    print('=' * 90)
    print(f'{"시나리오":<30s} {"영향":>5s} {"우선":>5s} {"보류":>5s} {"이동":>5s} {"통합":>5s} {"비용Δ":>10s}')
    print('─' * 90)
    for sid, res in results.items():
        s  = res['routy_input']['summary']
        sc = res['scenario']
        label = f'[{sid.split("_")[0]}] {sc["name"][:20]}'
        print(f'{label:<30s} {s["affected"]:>5d} {s["priority"]:>5d} '
              f'{s["holdback"]:>5d} {s["shifted"]:>5d} '
              f'{s["consolidation_groups"]:>5d} ${s["total_cost_delta_usd"]:>+9,d}')

    # 세부 시나리오 근거 출력
    print('\n[세부 시나리오 실제 근거]')
    for sub_id, sub in SUB_SCENARIOS.items():
        print(f'  {sub_id:<22s} {sub["name"]:<16s} +{sub["delay_days"]}일 / '
              f'+{sub["freight_surge_pct"]:.0%} | {sub["evidence"][:50]}')
