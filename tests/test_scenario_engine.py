"""tests/test_scenario_engine.py — 시나리오 엔진 단위 테스트"""
import pytest
from datetime import datetime
from src.scenario_engine import (
    auto_classify_scenario, analyze_impact, generate_shipments, calc_freight
)
from src.config import SCENARIOS


# ── 자동 분류기 ───────────────────────────────────────────────────────────────

def test_auto_classify_cancel_takes_priority():
    assert auto_classify_scenario(0.9, '지정학분쟁', cancel_count=1) == 'E_CANCELLATION'


def test_auto_classify_geopolitical():
    assert auto_classify_scenario(0.75, '지정학분쟁') == 'B_GEOPOLITICAL'


def test_auto_classify_weather():
    assert auto_classify_scenario(0.55, '기상재해') == 'C_WEATHER'


def test_auto_classify_delay_strike():
    assert auto_classify_scenario(0.40, '항만파업') == 'D_DELAY'


def test_auto_classify_normal():
    assert auto_classify_scenario(0.20, '정상') == 'A_NORMAL'


def test_auto_classify_mri_fallback():
    assert auto_classify_scenario(0.72, '정상') == 'B_GEOPOLITICAL'
    assert auto_classify_scenario(0.52, '정상') == 'C_WEATHER'
    assert auto_classify_scenario(0.35, '정상') == 'D_DELAY'
    assert auto_classify_scenario(0.25, '정상') == 'A_NORMAL'


# ── 시나리오 파라미터 검증 (PROJECT_SPEC.md 수치 일치) ────────────────────────

def test_scenario_b_params():
    b = SCENARIOS['B_GEOPOLITICAL']
    assert b['delay_days'] == 14
    assert b['freight_surge_pct'] == 0.30
    assert b['reroute_required'] is True
    assert '부산→로테르담' in b['affects_routes']


def test_scenario_c_params():
    c = SCENARIOS['C_WEATHER']
    assert c['delay_days'] == 5
    assert c['freight_surge_pct'] == 0.05
    assert c['cold_chain_priority'] is True


def test_scenario_d_params():
    d = SCENARIOS['D_DELAY']
    assert d['delay_days'] == 3
    assert d['freight_surge_pct'] == 0.02


# ── 영향 분석 ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_shipment():
    return {
        'shipment_id':    'SH-001',
        'company':        '화주_A',
        'route':          '부산→로테르담',
        'cargo_type':     '일반화물',
        'region':         '경기남부',
        'pickup_date':    datetime(2026, 5, 10),
        'cbm':            20.0,
        'deadline_days':  10,
        'urgent':         False,
        'estimated_cost': 2000,
    }


def test_a_scenario_no_effect(sample_shipment):
    ia = analyze_impact(sample_shipment, SCENARIOS['A_NORMAL'])
    assert ia.is_affected is False
    assert ia.delay_days_applied == 0
    assert ia.cost_delta == 0


def test_b_scenario_rotterdam_affected(sample_shipment):
    ia = analyze_impact(sample_shipment, SCENARIOS['B_GEOPOLITICAL'])
    assert ia.is_affected is True
    assert ia.delay_days_applied == 14
    assert ia.cost_delta == round(2000 * 0.30)


def test_b_scenario_other_route_not_affected(sample_shipment):
    sample_shipment['route'] = '부산→LA'
    ia = analyze_impact(sample_shipment, SCENARIOS['B_GEOPOLITICAL'])
    assert ia.is_affected is False


def test_b_scenario_deadline_violated(sample_shipment):
    ia = analyze_impact(sample_shipment, SCENARIOS['B_GEOPOLITICAL'])
    assert ia.deadline_violated is True   # 14일 > 10일


def test_c_scenario_cold_chain_priority():
    shipment = {
        'shipment_id':   'SH-999',
        'company':       '냉장화주',
        'route':         '부산→LA',
        'cargo_type':    '냉장화물',
        'region':        '경기남부',
        'pickup_date':   datetime(2026, 5, 10),
        'cbm':           10.0,
        'deadline_days': 20,
        'urgent':        False,
        'estimated_cost': 1000,
    }
    ia = analyze_impact(shipment, SCENARIOS['C_WEATHER'])
    assert ia.requires_priority is True


def test_e_scenario_cancellation():
    shipment = {
        'shipment_id':   'SH-005',
        'company':       '화주_E',
        'route':         '부산→LA',
        'cargo_type':    '일반화물',
        'region':        '충청',
        'pickup_date':   datetime(2026, 5, 10),
        'cbm':           15.0,
        'deadline_days': 14,
        'urgent':        False,
        'estimated_cost': 1500,
    }
    ia = analyze_impact(shipment, SCENARIOS['E_CANCELLATION'],
                        cancelled_ids={'SH-005'})
    assert ia.is_affected is True
    assert ia.new_estimated_cost == 0
    assert ia.cost_delta == -1500


def test_e_scenario_not_cancelled():
    shipment = {
        'shipment_id':   'SH-006',
        'company':       '화주_F',
        'route':         '부산→LA',
        'cargo_type':    '일반화물',
        'region':        '충청',
        'pickup_date':   datetime(2026, 5, 10),
        'cbm':           15.0,
        'deadline_days': 14,
        'urgent':        False,
        'estimated_cost': 1500,
    }
    ia = analyze_impact(shipment, SCENARIOS['E_CANCELLATION'],
                        cancelled_ids={'SH-005'})
    assert ia.is_affected is False


# ── 운임 계산 ─────────────────────────────────────────────────────────────────

def test_calc_freight_la():
    cost = calc_freight(33.0, '부산→LA')
    expected = round((2300 / 33) * 1.5 * 33)
    assert cost == expected


def test_generate_shipments_count():
    df = generate_shipments(n=30)
    assert len(df) == 30
    assert set(df.columns) >= {'shipment_id', 'company', 'route', 'cargo_type',
                                'region', 'pickup_date', 'cbm', 'deadline_days',
                                'urgent', 'estimated_cost'}
