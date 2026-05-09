"""
reorganizer.py — 운영 재조정 엔진
영향 분석 결과 → PRIORITY / HOLDBACK / SHIFT / CONSOLIDATION 4가지 행동 분류.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime

import pandas as pd

from src.config import CONSOLIDATION_SAVINGS_RATE, CARGO_COMPAT
from src.scenario_engine import ImpactAnalysis


@dataclass
class ConsolidationGroup:
    region:              str
    cargo_type:          str
    merged_pickup_date:  str   # 'YYYY-MM-DD'
    members:             list[str]
    companies:           list[str]
    total_cbm:           float
    savings_estimate_pct: float = CONSOLIDATION_SAVINGS_RATE


def reorganize_pickups(ship_df: pd.DataFrame,
                       impacts: list[ImpactAnalysis],
                       scenario: dict) -> dict:
    """
    영향 분석 결과를 4가지 행동으로 분류하고 권역 통합 그룹을 구성.

    반환 dict 키:
      pickup_holdback      — 항만 반입 보류 대상
      pickup_shifted       — 집화 일정 이동 대상
      pickup_priority      — 우선처리 대상
      consolidation_groups — 권역 통합 그룹 (ConsolidationGroup)
    """
    impact_map = {ia.shipment_id: ia for ia in impacts}

    pickup_holdback: list[dict] = []
    pickup_shifted:  list[dict] = []
    pickup_priority: list[dict] = []

    for _, ship in ship_df.iterrows():
        ia = impact_map[ship['shipment_id']]
        if not ia.is_affected:
            continue

        if ia.requires_priority:
            pickup_priority.append({
                'shipment_id':     ship['shipment_id'],
                'company':         ship['company'],
                'cargo_type':      ship['cargo_type'],
                'urgency_reason':  '냉장화물' if ship['cargo_type'] == '냉장화물' else '긴급',
                'new_pickup_date': ia.new_pickup_date.strftime('%Y-%m-%d'),
            })
        elif ia.requires_holdback:
            pickup_holdback.append({
                'shipment_id':     ship['shipment_id'],
                'company':         ship['company'],
                'original_pickup': ship['pickup_date'].strftime('%Y-%m-%d'),
                'reason':          f'출항 {ia.delay_days_applied}일 지연 — 항만 반입 보류',
            })
        else:
            pickup_shifted.append({
                'shipment_id':     ship['shipment_id'],
                'company':         ship['company'],
                'original_pickup': ship['pickup_date'].strftime('%Y-%m-%d'),
                'new_pickup':      ia.new_pickup_date.strftime('%Y-%m-%d'),
                'shift_days':      ia.delay_days_applied,
            })

    consolidation_groups = _build_consolidation_groups(
        ship_df, impact_map, {p['shipment_id'] for p in pickup_shifted}
    )

    return {
        'pickup_holdback':      pickup_holdback,
        'pickup_shifted':       pickup_shifted,
        'pickup_priority':      pickup_priority,
        'consolidation_groups': [asdict(g) for g in consolidation_groups],
    }


# ── 내부: 권역 통합 그룹 구성 ────────────────────────────────────────────────

def _cargo_compat(c1: str, c2: str) -> bool:
    return (c1, c2) in CARGO_COMPAT or (c2, c1) in CARGO_COMPAT


def _build_consolidation_groups(
    ship_df: pd.DataFrame,
    impact_map: dict[str, ImpactAnalysis],
    shifted_ids: set[str],
) -> list[ConsolidationGroup]:
    """
    집화이동 대상 중 권역·화물 호환·날짜 ±2일 조건을 만족하는 그룹 생성.
    최소 2건 이상이어야 그룹으로 인정.
    """
    candidates = ship_df[ship_df['shipment_id'].isin(shifted_ids)].copy()
    if candidates.empty:
        return []

    candidates['new_pickup'] = candidates['shipment_id'].map(
        lambda sid: impact_map[sid].new_pickup_date
    )

    groups: list[ConsolidationGroup] = []
    used: set[str] = set()

    for region in candidates['region'].unique():
        region_df = candidates[candidates['region'] == region].sort_values('new_pickup')
        for _, anchor in region_df.iterrows():
            if anchor['shipment_id'] in used:
                continue
            group_rows = [anchor]
            used.add(anchor['shipment_id'])
            for _, candidate in region_df.iterrows():
                if candidate['shipment_id'] in used:
                    continue
                date_diff = abs((candidate['new_pickup'] - anchor['new_pickup']).days)
                if date_diff <= 2 and _cargo_compat(anchor['cargo_type'], candidate['cargo_type']):
                    group_rows.append(candidate)
                    used.add(candidate['shipment_id'])

            if len(group_rows) >= 2:
                groups.append(ConsolidationGroup(
                    region=region,
                    cargo_type=anchor['cargo_type'],
                    merged_pickup_date=anchor['new_pickup'].strftime('%Y-%m-%d'),
                    members=[r['shipment_id'] for r in group_rows],
                    companies=[r['company'] for r in group_rows],
                    total_cbm=round(sum(r['cbm'] for r in group_rows), 1),
                ))

    return groups
