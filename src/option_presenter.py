"""
option_presenter.py — MRI 고위험 시 화주 대상 4가지 대응 옵션 제시
======================================================================
플랫폼은 추천만 제공. 화주가 선택. 강요 없음.

[옵션 정의]
A: 리스크 무시, 원래대로 직송        (기준선)
B: 최단 거리 창고/ODCY 임시 보관
C: 최저 비용 창고/ODCY 임시 보관
D: 거리 + 비용 종합 최적 (권장)

[비용 구성 요소]
- 루티 운송비 Phase1  : 출발지 → 창고/CY       (거리 기반)
- 루티 운송비 Phase2  : 창고 → CY              (A안은 0)
- 창고 대여비          : CBM × 지연일수 × 단가   (A안은 0)
- 창고 계약비          : 건당 고정비             (A안은 0)
- 해상 운임            : 공통 (옵션 간 동일)

[단가 기준 — 실제 부산항 주변 ODCY 평균 기준]
  루티 운송:  일반 $1.5/km, 냉장 $2.2/km, 위험물 $2.5/km
  창고 대여:  일반 $0.50/CBM/일, 냉장 $0.85/CBM/일, 위험물 $1.20/CBM/일
  계약비:     일반 $45, 냉장 $75, 위험물 $90 (건당 고정)
  Phase2:     창고→CY 평균 12km 기준으로 계산
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── 단가 테이블 ────────────────────────────────────────────────────────────────

_ROUTY_RATE: dict[str, float] = {
    '일반화물': 1.5,    # USD/km
    '냉장화물': 2.2,
    '위험물':   2.5,
}

_WAREHOUSE_DAILY: dict[str, float] = {
    '일반화물': 0.50,   # USD/CBM/일
    '냉장화물': 0.85,
    '위험물':   1.20,
}

_CONTRACT_FEE: dict[str, float] = {
    '일반화물': 45.0,   # USD/건
    '냉장화물': 75.0,
    '위험물':   90.0,
}

_PHASE2_AVG_KM = 12.0   # 창고→CY 평균 거리 (부산항 기준)


# ── 데이터 클래스 ──────────────────────────────────────────────────────────────

@dataclass
class OptionCost:
    option_id:            str             # 'A' ~ 'D'
    option_name:          str
    description:          str
    warehouse:            Optional[dict]  # None = A안
    mode:                 str             # 'direct'|'distance'|'cost'|'comprehensive'

    # 비용 항목 (USD)
    routy_phase1_usd:     float = 0.0    # 출발지 → 창고 or CY
    routy_phase2_usd:     float = 0.0    # 창고 → CY
    warehouse_rental_usd: float = 0.0
    warehouse_contract_usd: float = 0.0
    freight_usd:          float = 0.0    # 해상 운임 (공통)

    # 위험 부담 (A안만 해당 — 지연 시 재반입 비용 추정)
    risk_penalty_usd:     float = 0.0

    @property
    def total_usd(self) -> float:
        return (self.routy_phase1_usd + self.routy_phase2_usd
                + self.warehouse_rental_usd + self.warehouse_contract_usd
                + self.freight_usd + self.risk_penalty_usd)

    def savings_vs(self, baseline: 'OptionCost') -> float:
        """baseline(A안) 대비 절약액 (양수=절약, 음수=추가비용)."""
        return baseline.total_usd - self.total_usd

    def savings_pct_vs(self, baseline: 'OptionCost') -> float:
        if baseline.total_usd == 0:
            return 0.0
        return self.savings_vs(baseline) / baseline.total_usd * 100


# ── 비용 산출 헬퍼 ─────────────────────────────────────────────────────────────

def _routy_cost(km: float, cargo_type: str) -> float:
    rate = _ROUTY_RATE.get(cargo_type, 1.5)
    return round(km * rate, 2)


def _warehouse_cost(cbm: float, delay_days: int, cargo_type: str) -> tuple[float, float]:
    """(대여비, 계약비) 반환."""
    daily = _WAREHOUSE_DAILY.get(cargo_type, 0.50)
    rental   = round(cbm * delay_days * daily, 2)
    contract = _CONTRACT_FEE.get(cargo_type, 45.0)
    return rental, contract


def _pick_warehouse(storage_result: dict, mode: str) -> Optional[dict]:
    """odcy_recommender.recommend_storage() 결과에서 모드별 1위 창고 선택."""
    mode_map = {
        'distance':     'distance',
        'cost':         'time',           # time ≈ 비용 최소 (가까울수록 저렴)
        'comprehensive': 'comprehensive',
    }
    key = mode_map.get(mode, 'comprehensive')
    items = storage_result.get('recommendations', {}).get(key, [])
    return items[0] if items else None


# ── 메인 함수 ──────────────────────────────────────────────────────────────────

def generate_four_options(
    shipment: dict,
    storage_result: dict,
    delay_days: int,
    freight_usd: int,
    phase1_origin_km: Optional[float] = None,   # 출발지→항만 직선거리 (없으면 추정)
) -> list[OptionCost]:
    """
    화주 1건에 대해 A/B/C/D 4가지 옵션과 비용을 산출합니다.

    Parameters
    ----------
    shipment        : generate_shipments() 행 또는 화주 입력 dict
                      필수 키: cargo_type, cbm, region
    storage_result  : odcy_recommender.recommend_storage() 반환값
    delay_days      : 해당 시나리오의 예상 지연 일수
    freight_usd     : 원래 해상 운임 (USD)
    phase1_origin_km: 출발지→창고 거리 (없으면 권역별 평균값 사용)

    Returns
    -------
    list[OptionCost] : [A, B, C, D] 순서
    """
    cargo  = str(shipment.get('cargo_type', '일반화물'))
    cbm    = float(shipment.get('cbm', 15.0))
    region = str(shipment.get('region', '경기남부'))

    # 권역별 항만까지 평균 거리 (km) — 출발지→CY 직송 기준
    REGION_TO_PORT: dict[str, float] = {
        '경기남부': 380.0,
        '경기북부': 410.0,
        '충청':    280.0,
        '경상남부':  60.0,
        '경상북부': 130.0,
    }
    direct_km = phase1_origin_km or REGION_TO_PORT.get(region, 300.0)

    # A안 — 리스크 무시 직송
    # 지연 발생 시 항만에서 재반입 또는 체선료 발생 가능 → 위험 부담 추정
    risk_penalty = round(cbm * delay_days * _WAREHOUSE_DAILY.get(cargo, 0.50) * 1.5, 2)
    opt_a = OptionCost(
        option_id='A',
        option_name='리스크 무시 — 원래대로 직송',
        description=f'현재 계획대로 CY에 직접 반입. 지연 {delay_days}일 감수.',
        warehouse=None,
        mode='direct',
        routy_phase1_usd=_routy_cost(direct_km, cargo),
        routy_phase2_usd=0.0,
        warehouse_rental_usd=0.0,
        warehouse_contract_usd=0.0,
        freight_usd=float(freight_usd),
        risk_penalty_usd=risk_penalty,
    )

    options = [opt_a]

    # B/C/D — 창고 보관 옵션
    for opt_id, opt_name, desc, mode in [
        ('B', '최단 거리 창고 보관',       '가장 가까운 창고·ODCY에 임시 보관 후 재반입.',   'distance'),
        ('C', '최저 비용 창고 보관',       '운송비+보관비 합산 최저 창고·ODCY 선택.',        'cost'),
        ('D', '거리+비용 종합 최적 (권장)', '거리·비용·시설 등급을 종합 고려한 최적 창고.', 'comprehensive'),
    ]:
        wh = _pick_warehouse(storage_result, mode)
        if wh is None:
            continue

        wh_km    = float(wh.get('distance_km') or 15.0)   # 항만→창고
        phase1   = _routy_cost(direct_km * 0.85 + wh_km, cargo)  # 출발지→창고 (항만 방향)
        phase2   = _routy_cost(_PHASE2_AVG_KM, cargo)             # 창고→CY
        rental, contract = _warehouse_cost(cbm, delay_days, cargo)

        options.append(OptionCost(
            option_id=opt_id,
            option_name=opt_name,
            description=f'{desc}  [{wh.get("name", "창고")} / {wh_km:.1f}km]',
            warehouse=wh,
            mode=mode,
            routy_phase1_usd=phase1,
            routy_phase2_usd=phase2,
            warehouse_rental_usd=rental,
            warehouse_contract_usd=contract,
            freight_usd=float(freight_usd),
            risk_penalty_usd=0.0,
        ))

    return options


# ── 출력 포매터 ────────────────────────────────────────────────────────────────

def format_option_table(options: list[OptionCost]) -> str:
    """
    콘솔 출력용 옵션 비교표.
    """
    if not options:
        return '옵션 없음'

    baseline = options[0]   # A안

    lines = [
        '=' * 72,
        '  화주 대응 옵션 비교  (플랫폼 추천 — 최종 결정은 화주)',
        '=' * 72,
        f'  {"옵션":<6} {"설명":<28} {"루티P1":>7} {"루티P2":>7} '
        f'{"창고대여":>8} {"계약비":>7} {"리스크":>7} {"합계":>8} {"A대비":>9}',
        '-' * 72,
    ]

    for opt in options:
        sav     = opt.savings_vs(baseline)
        sav_pct = opt.savings_pct_vs(baseline)
        sav_str = (f'+${abs(sav):,.0f}↑' if sav < 0 else f'-${sav:,.0f}↓') if opt.option_id != 'A' else '기준'
        risk_str = f'${opt.risk_penalty_usd:,.0f}' if opt.risk_penalty_usd else '  $0'

        star = ' ★' if opt.option_id == 'D' else '  '
        lines.append(
            f'{star}{opt.option_id}안  {opt.option_name[:26]:<26}  '
            f'${opt.routy_phase1_usd:>5,.0f}  '
            f'${opt.routy_phase2_usd:>5,.0f}  '
            f'${opt.warehouse_rental_usd:>6,.0f}  '
            f'${opt.warehouse_contract_usd:>5,.0f}  '
            f'{risk_str:>7}  '
            f'${opt.total_usd:>6,.0f}  '
            f'{sav_str:>9}'
        )

    lines += [
        '-' * 72,
        '  ★ D안 권장  |  A안 리스크 비용 = 지연 시 체선료·재반입비 추정',
        '  ※ 루티P1=출발지→창고/CY, 루티P2=창고→CY, 창고대여=일수×CBM×단가',
        '=' * 72,
    ]
    return '\n'.join(lines)


def format_option_detail(opt: OptionCost, baseline: OptionCost) -> str:
    """선택된 옵션의 상세 안내문 (화주 홈페이지/앱 노출용)."""
    sav = opt.savings_vs(baseline)
    wh  = opt.warehouse

    lines = [
        f'📦 선택 옵션: {opt.option_id}안 — {opt.option_name}',
        f'   {opt.description}',
        '',
        '💰 비용 상세',
        f'   루티 운송 (Phase 1): ${opt.routy_phase1_usd:,.0f}',
    ]
    if opt.routy_phase2_usd:
        lines.append(f'   루티 운송 (Phase 2): ${opt.routy_phase2_usd:,.0f}')
    if opt.warehouse_rental_usd:
        lines.append(f'   창고 대여비:          ${opt.warehouse_rental_usd:,.0f}')
    if opt.warehouse_contract_usd:
        lines.append(f'   창고 계약비:          ${opt.warehouse_contract_usd:,.0f}')
    lines += [
        f'   해상 운임:            ${opt.freight_usd:,.0f}',
        f'   ──────────────────────────',
        f'   합계:                 ${opt.total_usd:,.0f}',
    ]
    if opt.option_id != 'A':
        sign = '절약' if sav >= 0 else '추가'
        lines.append(f'   A안 대비:             {sign} ${abs(sav):,.0f}  ({abs(opt.savings_pct_vs(baseline)):.1f}%)')

    if wh:
        lines += [
            '',
            f'🏭 추천 창고·ODCY',
            f'   {wh.get("name", "")}',
            f'   주소: {wh.get("address", "")}',
            f'   항만까지: {wh.get("distance_km", "?"):.1f}km / {wh.get("duration_min", "?"):.0f}분',
            f'   운영: {wh.get("operating_hours", "")}',
        ]
    return '\n'.join(lines)
