"""
scenario_engine.py — 시나리오 자동 분류기 + 영향 분석 엔진
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from src.config import SCENARIOS, SUB_SCENARIOS, ROUTE_INFO, LCL_MULTIPLIER


# ── 데이터 클래스 ─────────────────────────────────────────────────────────────

@dataclass
class ShipmentRequest:
    shipment_id:     str
    company:         str
    route:           str        # ROUTE_INFO 키와 일치
    cargo_type:      str        # '일반화물' / '냉장화물' / '위험물'
    region:          str        # '경기남부' 등
    pickup_date:     datetime
    cbm:             float
    deadline_days:   int        # 납기 허용 일수
    urgent:          bool
    estimated_cost:  int        # 예상 운임 (USD)


@dataclass
class ImpactAnalysis:
    shipment_id:         str
    is_affected:         bool
    delay_days_applied:  int
    new_pickup_date:     datetime
    new_estimated_cost:  int
    cost_delta:          int
    deadline_violated:   bool
    requires_holdback:   bool
    requires_priority:   bool
    reason:              str
    sub_scenario_id:     str | None = None   # 세부 시나리오 ID (예: B1_RED_SEA)
    sub_scenario_name:   str | None = None   # 세부 시나리오 한글명


# ── 시나리오 자동 분류기 ──────────────────────────────────────────────────────

def auto_classify_scenario(today_mri: float,
                            top_category: str,
                            cancel_count: int = 0) -> str:
    """
    Part 1 MRI + NLP 카테고리 → 시나리오 ID 반환.
    우선순위: 취소 > 카테고리+MRI > MRI 단독 fallback
    """
    if cancel_count > 0:
        return 'E_CANCELLATION'

    if top_category == '지정학분쟁' and today_mri >= 0.7:
        return 'B_GEOPOLITICAL'
    if top_category == '기상재해' and today_mri >= 0.5:
        return 'C_WEATHER'
    if top_category in ('항만파업', '관세정책', '운임급등') and today_mri >= 0.3:
        return 'D_DELAY'
    if today_mri < 0.3:
        return 'A_NORMAL'

    # MRI 단독 fallback
    if today_mri >= 0.7:
        return 'B_GEOPOLITICAL'
    if today_mri >= 0.5:
        return 'C_WEATHER'
    if today_mri >= 0.3:
        return 'D_DELAY'
    return 'A_NORMAL'


# ── 세부 시나리오 분류기 ──────────────────────────────────────────────────────

def auto_classify_sub_scenario(
    scenario_id: str,
    top_category: str,
    news_keywords: list[str] | None = None,
) -> str | None:
    """
    메인 시나리오 ID → 실제 사례 기반 세부 시나리오 ID 반환.

    B_GEOPOLITICAL: B1(홍해) / B2(호르무즈) / B3(미중관세) 구분
    C_WEATHER:      C1(태풍) / C2(운하수위) 구분
    D_DELAY:        D1(파업) / D2(관세통관) / D3(운임급등) 구분
    A/E: 세부 분류 없음 → None 반환

    근거: 동일 지정학 위기라도 홍해(유럽항로)·호르무즈(중동항로)·
    미중관세(미주항로)는 영향 항로·지연일수·운임 증가율이 다름.
    """
    # 소문자 단어셋 — 뉴스 제목 split() 결과와 매칭
    # 주의: 'Red Sea', 'El Niño' 같은 다중단어는 split() 후 교집합 누락됨
    #       → 소문자 단일 토큰으로 통일
    kw = {w.lower() for w in (news_keywords or [])}

    if scenario_id == 'B_GEOPOLITICAL':
        if kw & {'홍해', '후티', '수에즈', '후티반군',
                 'houthi', 'houthis', 'suez', 'aden', 'jeddah'}:
            return 'B1_RED_SEA'
        if kw & {'호르무즈', '이란', '페르시아', '이란핵',
                 'hormuz', 'iran', 'iranian', 'persian', 'strait'}:
            return 'B2_HORMUZ'
        if kw & {'미중', '관세전쟁', '트럼프', '145%', '보복관세',
                 'tariff', 'trump', 'china', 'us-china', 'trade'}:
            return 'B3_TARIFF_WAR'
        return 'B1_RED_SEA'   # 최근 가장 빈번한 지정학 사례 기본값

    if scenario_id == 'C_WEATHER':
        if kw & {'운하', '수위', '가뭄', '엘니뇨', '파나마', '수에즈수위',
                 'canal', 'panama', 'drought', 'nino', 'water', 'level'}:
            return 'C2_CANAL_DROUGHT'
        return 'C1_TYPHOON'   # 태풍이 기상재해 기본값

    if scenario_id == 'D_DELAY':
        if top_category == '항만파업':
            return 'D1_PORT_STRIKE'
        if top_category == '관세정책':
            return 'D2_TARIFF_DELAY'
        if top_category == '운임급등':
            return 'D3_FREIGHT_SURGE'
        return 'D1_PORT_STRIKE'

    return None


# ── 운임 계산 ─────────────────────────────────────────────────────────────────

def calc_freight(cbm: float, route: str) -> int:
    info = ROUTE_INFO[route]
    fcl_per_cbm = info['usd_per_teu'] / 33  # 1 TEU ≈ 33 CBM
    return round(fcl_per_cbm * LCL_MULTIPLIER * cbm)


# ── 출하 예정 건 시뮬 생성 ────────────────────────────────────────────────────

def generate_shipments(n: int = 30,
                       base_date: datetime | None = None,
                       seed: int = 42) -> pd.DataFrame:
    """시뮬레이션용 출하 예정 건 N개 생성."""
    import numpy as np
    import random
    from src.config import REGIONS, CARGO_TYPES, CARGO_TYPE_PROBS

    np.random.seed(seed)
    random.seed(seed)

    if base_date is None:
        base_date = datetime(2026, 5, 1)

    routes = list(ROUTE_INFO.keys())
    records = []
    for i in range(n):
        route      = np.random.choice(routes)
        cargo_type = np.random.choice(CARGO_TYPES, p=CARGO_TYPE_PROBS)
        region     = np.random.choice(REGIONS)
        pickup     = base_date + timedelta(days=int(np.random.randint(2, 16)))
        cbm        = round(float(np.random.uniform(5, 35)), 1)
        deadline   = int(np.random.choice([7, 10, 14, 21], p=[0.2, 0.3, 0.3, 0.2]))
        urgent     = bool(np.random.random() < 0.15)
        records.append({
            'shipment_id':    f'SH-{i+1:03d}',
            'company':        f'화주_{chr(65+i)}',
            'route':          route,
            'cargo_type':     cargo_type,
            'region':         region,
            'pickup_date':    pickup,
            'cbm':            cbm,
            'deadline_days':  deadline,
            'urgent':         urgent,
            'estimated_cost': calc_freight(cbm, route),
        })
    return pd.DataFrame(records)


# ── 영향 분석 ─────────────────────────────────────────────────────────────────

def _as_planned(shipment: dict) -> ImpactAnalysis:
    return ImpactAnalysis(
        shipment_id=shipment['shipment_id'],
        is_affected=False,
        delay_days_applied=0,
        new_pickup_date=shipment['pickup_date'],
        new_estimated_cost=shipment['estimated_cost'],
        cost_delta=0,
        deadline_violated=False,
        requires_holdback=False,
        requires_priority=False,
        reason='평상시 — 기존 계획 유지',
    )


def analyze_impact(shipment: dict,
                   scenario: dict,
                   cancelled_ids: set | None = None,
                   sub_scenario_id: str | None = None) -> ImpactAnalysis:
    """단일 출하 건에 시나리오 영향을 적용해 ImpactAnalysis 반환."""
    cancelled_ids = cancelled_ids or set()

    if scenario['policy'] == 'REGROUP_REMAINING':
        if shipment['shipment_id'] in cancelled_ids:
            return ImpactAnalysis(
                shipment_id=shipment['shipment_id'],
                is_affected=True,
                delay_days_applied=0,
                new_pickup_date=shipment['pickup_date'],
                new_estimated_cost=0,
                cost_delta=-shipment['estimated_cost'],
                deadline_violated=False,
                requires_holdback=False,
                requires_priority=False,
                reason='주문 취소 — 매칭 그룹에서 제외',
            )
        return _as_planned(shipment)

    if scenario['policy'] == 'AS_PLANNED':
        return _as_planned(shipment)

    # B 시나리오: 특정 항로만
    if scenario['affects_routes'] and shipment['route'] not in scenario['affects_routes']:
        return ImpactAnalysis(
            shipment_id=shipment['shipment_id'],
            is_affected=False,
            delay_days_applied=0,
            new_pickup_date=shipment['pickup_date'],
            new_estimated_cost=shipment['estimated_cost'],
            cost_delta=0,
            deadline_violated=False,
            requires_holdback=False,
            requires_priority=False,
            reason=f'영향권 외 항로 ({shipment["route"]})',
        )

    # 세부 시나리오 파라미터 우선 적용 (있으면 메인 시나리오 수치를 덮어씀)
    sub = SUB_SCENARIOS.get(sub_scenario_id) if sub_scenario_id else None
    delay  = sub['delay_days']          if sub else scenario['delay_days']
    surge  = sub['freight_surge_pct']   if sub else scenario['freight_surge_pct']

    # 세부 시나리오의 영향 항로 재검사 (affects_routes가 있으면 덮어씀)
    sub_routes = sub.get('affects_routes') if sub else None
    effective_routes = sub_routes if sub_routes is not None else scenario['affects_routes']
    if effective_routes and shipment['route'] not in effective_routes:
        return ImpactAnalysis(
            shipment_id=shipment['shipment_id'],
            is_affected=False,
            delay_days_applied=0,
            new_pickup_date=shipment['pickup_date'],
            new_estimated_cost=shipment['estimated_cost'],
            cost_delta=0,
            deadline_violated=False,
            requires_holdback=False,
            requires_priority=False,
            reason=f'영향권 외 항로 ({shipment["route"]})',
            sub_scenario_id=sub_scenario_id,
            sub_scenario_name=sub['name'] if sub else None,
        )

    new_date   = shipment['pickup_date'] + timedelta(days=delay)
    new_cost   = round(shipment['estimated_cost'] * (1 + surge))
    cost_delta = new_cost - shipment['estimated_cost']

    deadline_violated = delay > shipment['deadline_days']
    requires_holdback = delay >= 3 and not shipment['urgent']
    cold_prio = (sub or scenario).get('cold_chain_priority', False)
    requires_priority = (cold_prio and shipment['cargo_type'] == '냉장화물') or shipment['urgent']

    reason = f'{sub["name"] if sub else scenario["name"]} — 지연 {delay}일'
    if surge > 0:
        reason += f', 운임 +{surge:.0%}'
    reroute = sub.get('reroute_via') if sub else None
    if reroute:
        reason += f', {reroute}'
    elif scenario.get('reroute_required'):
        reason += ', 우회항로'

    return ImpactAnalysis(
        shipment_id=shipment['shipment_id'],
        is_affected=True,
        delay_days_applied=delay,
        new_pickup_date=new_date,
        new_estimated_cost=new_cost,
        cost_delta=cost_delta,
        deadline_violated=deadline_violated,
        requires_holdback=requires_holdback,
        requires_priority=requires_priority,
        reason=reason,
        sub_scenario_id=sub_scenario_id,
        sub_scenario_name=sub['name'] if sub else None,
    )


def analyze_all(ship_df: pd.DataFrame,
                scenario_id: str,
                cancelled_ids: set | None = None) -> list[ImpactAnalysis]:
    """DataFrame 전체 출하 건에 시나리오를 적용해 ImpactAnalysis 리스트 반환."""
    scenario = SCENARIOS[scenario_id]
    return [
        analyze_impact(row, scenario, cancelled_ids)
        for row in ship_df.to_dict('records')
    ]
