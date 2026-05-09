"""tests/test_reorganizer.py — 운영 재조정 엔진 단위 테스트"""
import pytest
from datetime import datetime
import pandas as pd

from src.scenario_engine import analyze_impact, generate_shipments
from src.reorganizer import reorganize_pickups
from src.config import SCENARIOS


@pytest.fixture
def ship_df():
    return generate_shipments(n=30, seed=42)


def test_a_scenario_no_reorg(ship_df):
    impacts = [analyze_impact(s, SCENARIOS['A_NORMAL']) for s in ship_df.to_dict('records')]
    reorg   = reorganize_pickups(ship_df, impacts, SCENARIOS['A_NORMAL'])
    assert len(reorg['pickup_priority']) == 0
    assert len(reorg['pickup_holdback']) == 0
    assert len(reorg['pickup_shifted'])  == 0
    assert len(reorg['consolidation_groups']) == 0


def test_b_scenario_only_rotterdam(ship_df):
    impacts = [analyze_impact(s, SCENARIOS['B_GEOPOLITICAL']) for s in ship_df.to_dict('records')]
    affected_routes = [
        s['route'] for s, ia in zip(ship_df.to_dict('records'), impacts) if ia.is_affected
    ]
    assert all(r == '부산→로테르담' for r in affected_routes)


def test_c_scenario_cold_chain_priority(ship_df):
    impacts = [analyze_impact(s, SCENARIOS['C_WEATHER']) for s in ship_df.to_dict('records')]
    reorg   = reorganize_pickups(ship_df, impacts, SCENARIOS['C_WEATHER'])
    for p in reorg['pickup_priority']:
        sid  = p['shipment_id']
        row  = ship_df[ship_df['shipment_id'] == sid].iloc[0]
        assert row['cargo_type'] == '냉장화물' or row['urgent']


def test_consolidation_group_min_2(ship_df):
    impacts = [analyze_impact(s, SCENARIOS['D_DELAY']) for s in ship_df.to_dict('records')]
    reorg   = reorganize_pickups(ship_df, impacts, SCENARIOS['D_DELAY'])
    for g in reorg['consolidation_groups']:
        assert len(g['members']) >= 2


def test_consolidation_same_region(ship_df):
    impacts = [analyze_impact(s, SCENARIOS['D_DELAY']) for s in ship_df.to_dict('records')]
    reorg   = reorganize_pickups(ship_df, impacts, SCENARIOS['D_DELAY'])
    for g in reorg['consolidation_groups']:
        # 그룹 내 멤버 지역이 모두 같아야 함
        members = g['members']
        regions = ship_df[ship_df['shipment_id'].isin(members)]['region'].unique()
        assert len(regions) == 1
        assert regions[0] == g['region']
