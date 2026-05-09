"""tests/test_routy_adapter.py — 루티 JSON 출력 단위 테스트"""
import pytest
import json
import tempfile
from pathlib import Path

from src.scenario_engine import generate_shipments, analyze_impact
from src.reorganizer import reorganize_pickups
from src.routy_adapter import generate_routy_input, save_routy_json
from src.config import SCENARIOS


@pytest.fixture
def ship_df():
    return generate_shipments(n=30, seed=42)


def _make_routy(ship_df, scenario_id: str):
    scenario = SCENARIOS[scenario_id]
    impacts  = [analyze_impact(s, scenario) for s in ship_df.to_dict('records')]
    reorg    = reorganize_pickups(ship_df, impacts, scenario)
    return generate_routy_input(scenario_id, scenario, ship_df, impacts, reorg)


def test_execution_group_id_format(ship_df):
    routy = _make_routy(ship_df, 'B_GEOPOLITICAL')
    eid   = routy['execution_group_id']
    assert eid.startswith('EG-')
    assert 'B_GEOPOLITICAL' in eid


def test_meta_simulation_mode(ship_df):
    for sid in SCENARIOS:
        routy = _make_routy(ship_df, sid)
        assert routy['meta']['integration_status'] == 'simulation_mode'


def test_summary_total_matches_df(ship_df):
    routy = _make_routy(ship_df, 'C_WEATHER')
    assert routy['summary']['total_shipments'] == len(ship_df)


def test_summary_action_counts_consistent(ship_df):
    routy = _make_routy(ship_df, 'D_DELAY')
    s = routy['summary']
    assert s['priority'] + s['holdback'] + s['shifted'] == s['affected']


def test_save_routy_json(ship_df):
    routy = _make_routy(ship_df, 'A_NORMAL')
    with tempfile.TemporaryDirectory() as tmpdir:
        fp = save_routy_json(routy, Path(tmpdir))
        assert fp.exists()
        with open(fp, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded['execution_group_id'] == routy['execution_group_id']


def test_a_scenario_zero_affected(ship_df):
    routy = _make_routy(ship_df, 'A_NORMAL')
    assert routy['summary']['affected'] == 0
    assert routy['summary']['total_cost_delta_usd'] == 0


def test_b_scenario_cost_delta_positive(ship_df):
    routy = _make_routy(ship_df, 'B_GEOPOLITICAL')
    # 부산→로테르담 건이 있으면 비용 증가
    if routy['summary']['affected'] > 0:
        assert routy['summary']['total_cost_delta_usd'] > 0
