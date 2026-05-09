"""
routy_adapter.py — 위밋 루티/루티프로 API 입력용 표준 JSON 생성 어댑터
integration_status = 'simulation_mode' (실서비스 시 'live_api' 전환)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.scenario_engine import ImpactAnalysis


def generate_routy_input(
    scenario_id: str,
    scenario: dict,
    ship_df: pd.DataFrame,
    impacts: list[ImpactAnalysis],
    reorg: dict,
) -> dict:
    """
    루티 API 입력용 표준 JSON dict 반환.
    파일명 형식: EG-YYYYMMDD-{SCENARIO_ID}.json
    """
    impact_map = {ia.shipment_id: ia for ia in impacts}

    pickup_adjustments = []
    for _, s in ship_df.iterrows():
        ia = impact_map[s['shipment_id']]
        if not ia.is_affected:
            continue

        if ia.requires_priority:
            action = 'PRIORITY'
        elif ia.requires_holdback:
            action = 'HOLDBACK'
        else:
            action = 'SHIFT'

        pickup_adjustments.append({
            'shipment_id':       s['shipment_id'],
            'company':           s['company'],
            'region':            s['region'],
            'cbm':               float(s['cbm']),
            'cargo_type':        s['cargo_type'],
            'route':             s['route'],
            'original_pickup':   s['pickup_date'].strftime('%Y-%m-%d'),
            'adjusted_pickup':   ia.new_pickup_date.strftime('%Y-%m-%d'),
            'action':            action,
            'cost_delta_usd':    int(ia.cost_delta),
            'deadline_violated': bool(ia.deadline_violated),
            'cold_chain':        s['cargo_type'] == '냉장화물',
        })

    return {
        'execution_group_id': f'EG-{datetime.today().strftime("%Y%m%d")}-{scenario_id}',
        'generated_at':       datetime.today().isoformat(timespec='seconds'),
        'scenario': {
            'id':          scenario_id,
            'name':        scenario['name'],
            'icon':        scenario['icon'],
            'policy':      scenario['policy'],
            'description': scenario['description'],
        },
        'summary': {
            'total_shipments':      int(len(ship_df)),
            'affected':             int(sum(1 for ia in impacts if ia.is_affected)),
            'priority':             int(len(reorg['pickup_priority'])),
            'holdback':             int(len(reorg['pickup_holdback'])),
            'shifted':              int(len(reorg['pickup_shifted'])),
            'consolidation_groups': int(len(reorg['consolidation_groups'])),
            'total_cost_delta_usd': int(sum(ia.cost_delta for ia in impacts)),
            'deadline_violations':  int(sum(1 for ia in impacts if ia.deadline_violated)),
        },
        'pickup_adjustments':   pickup_adjustments,
        'consolidation_groups': reorg['consolidation_groups'],
        'priority_routing':     [p['shipment_id'] for p in reorg['pickup_priority']],
        'holdback_list':        [p['shipment_id'] for p in reorg['pickup_holdback']],
        'cargo_special_handling': {
            'cold_chain_count': int((ship_df['cargo_type'] == '냉장화물').sum()),
            'hazardous_count':  int((ship_df['cargo_type'] == '위험물').sum()),
        },
        'meta': {
            'note':               '본 출력은 위밋 루티/루티프로 API 입력 스펙으로 설계됨',
            'integration_status': 'simulation_mode',
            'next_step_api':      'POST /v1/dispatch/execute',
        },
    }


def save_routy_json(routy_input: dict, output_dir: Path) -> Path:
    """JSON을 routy_inputs/ 폴더에 저장하고 경로 반환."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fp = output_dir / f'{routy_input["execution_group_id"]}.json'
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(routy_input, f, ensure_ascii=False, indent=2, default=str)
    return fp


def run_all_scenarios(
    ship_df: pd.DataFrame,
    scenarios: dict,
    cancelled_ids: set | None = None,
    output_dir: Path | None = None,
) -> dict[str, dict]:
    """
    5개 시나리오를 일괄 실행하고 결과 dict 반환.
    output_dir 지정 시 JSON 파일 저장.
    """
    from src.scenario_engine import analyze_impact
    from src.reorganizer import reorganize_pickups

    cancelled_ids = cancelled_ids or set()
    results: dict[str, dict] = {}

    for scenario_id, scenario in scenarios.items():
        impacts = [
            analyze_impact(s, scenario, cancelled_ids)
            for s in ship_df.to_dict('records')
        ]
        reorg  = reorganize_pickups(ship_df, impacts, scenario)
        routy  = generate_routy_input(scenario_id, scenario, ship_df, impacts, reorg)

        if output_dir:
            save_routy_json(routy, output_dir)

        results[scenario_id] = {
            'scenario': scenario,
            'impacts':  impacts,
            'reorg':    reorg,
            'routy_input': routy,
        }

    return results
