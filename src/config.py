"""
config.py — 시나리오 정의, 항로 정보, MRI 가중치 등 전역 상수
PROJECT_SPEC.md 섹션 1·4·6·7 기준 (수치 변경 금지)
"""
from __future__ import annotations
from typing import Final

# ── 시나리오 5종 ──────────────────────────────────────────────────────────────
SCENARIOS: Final[dict] = {
    'A_NORMAL': {
        'name': '평상시 운영',
        'icon': '🟢',
        'color': '#4CAF50',
        'trigger': 'MRI < 0.3 + 정상 카테고리',
        'description': '리스크 신호 없음. 기존 계획대로 운송 실행.',
        'delay_days': 0,
        'freight_surge_pct': 0.0,
        'reroute_required': False,
        'cold_chain_priority': False,
        'affects_routes': [],
        'policy': 'AS_PLANNED',
    },
    'B_GEOPOLITICAL': {
        'name': '지정학 분쟁 (호르무즈/홍해)',
        'icon': '🔴',
        'color': '#D32F2F',
        'trigger': 'MRI ≥ 0.7 + 지정학분쟁',
        'description': '항로 봉쇄·전쟁 위험. 케이프타운 우회 + 운임 +30% (실제 홍해 사태 사례).',
        'delay_days': 14,           # 케이프타운 우회 실제 소요일
        'freight_surge_pct': 0.30,  # 2023~2024 홍해 사태 실제 +30%
        'reroute_required': True,
        'cold_chain_priority': True,
        'affects_routes': ['부산→로테르담'],
        'policy': 'REROUTE_AND_HOLDBACK',
    },
    'C_WEATHER': {
        'name': '기상 악화 (태풍/폭풍)',
        'icon': '🟠',
        'color': '#F57C00',
        'trigger': 'MRI ≥ 0.5 + 기상재해',
        'description': '단기 출항 지연 5일. 콜드체인 우선 처리, 일반화물 보류.',
        'delay_days': 5,
        'freight_surge_pct': 0.05,
        'reroute_required': False,
        'cold_chain_priority': True,
        'affects_routes': [],
        'policy': 'HOLDBACK_NORMAL_RUSH_COLD',
    },
    'D_DELAY': {
        'name': '단순 출항 지연',
        'icon': '🟡',
        'color': '#FBC02D',
        'trigger': 'MRI 0.3~0.5 + 파업/관세/운임급등',
        'description': '항만 혼잡·파업·운임 변동 등 일반 지연 3일. 집화 일정 조정.',
        'delay_days': 3,
        'freight_surge_pct': 0.02,
        'reroute_required': False,
        'cold_chain_priority': False,
        'affects_routes': [],
        'policy': 'SHIFT_PICKUP',
    },
    'E_CANCELLATION': {
        'name': '고객 단순 변심 (주문 취소)',
        'icon': '⚪',
        'color': '#9E9E9E',
        'trigger': '특정 주문 cancel_flag = True',
        'description': '단일 화주 출하 취소. 잔여 화물로 매칭 그룹 재구성.',
        'delay_days': 0,
        'freight_surge_pct': 0.0,
        'reroute_required': False,
        'cold_chain_priority': False,
        'affects_routes': [],
        'policy': 'REGROUP_REMAINING',
    },
}

# ── 세부 시나리오 (실제 사례 기반 세분화) ────────────────────────────────────
# 근거: UNCTAD 해운 보고서, KMI 분석, 실제 사건 통계
SUB_SCENARIOS: Final[dict] = {
    # B 세분류 — 지정학 분쟁 유형별
    'B1_RED_SEA': {
        'parent': 'B_GEOPOLITICAL',
        'name': '홍해/수에즈 봉쇄',
        'color': '#C62828',
        'trigger': 'MRI ≥ 0.7 + 후티/홍해/수에즈 키워드',
        'evidence': '2023.12~ 후티반군 공격 — 수에즈 통항량 42% 감소 (UNCTAD 2024)',
        'delay_days': 14,
        'freight_surge_pct': 0.30,
        'affects_routes': ['부산→로테르담'],
        'reroute_via': '케이프타운 우회 (+14일, +11,000 km)',
        'cold_chain_priority': True,
    },
    'B2_HORMUZ': {
        'parent': 'B_GEOPOLITICAL',
        'name': '호르무즈 봉쇄',
        'color': '#B71C1C',
        'trigger': 'MRI ≥ 0.7 + 이란/호르무즈 키워드',
        'evidence': 'UNCTAD 2019 — 호르무즈 통과 세계 LNG 20%·석유 21%, 원유가 직결',
        'delay_days': 10,
        'freight_surge_pct': 0.25,
        'affects_routes': ['부산→싱가포르'],
        'reroute_via': '오만만 우회 (+4일)',
        'cold_chain_priority': True,
    },
    'B3_TARIFF_WAR': {
        'parent': 'B_GEOPOLITICAL',
        'name': '미중 관세전쟁',
        'color': '#E65100',
        'trigger': 'MRI ≥ 0.5 + 미중/관세전쟁 키워드',
        'evidence': '2025.04 미국 대중 관세 145% — 미국행 중국발 예약 취소 급증, 선복 재배분',
        'delay_days': 7,
        'freight_surge_pct': 0.15,
        'affects_routes': ['부산→LA'],
        'reroute_via': None,
        'cold_chain_priority': False,
    },
    # C 세분류 — 기상재해 유형별
    'C1_TYPHOON': {
        'parent': 'C_WEATHER',
        'name': '태풍 직격',
        'color': '#E65100',
        'trigger': 'MRI ≥ 0.5 + 태풍/강풍 키워드 (6~9월)',
        'evidence': 'KMA 태풍 통계 2015-2024 — 부산항 입출항 평균 지연 4.8일',
        'delay_days': 5,
        'freight_surge_pct': 0.05,
        'affects_routes': [],
        'cold_chain_priority': True,
    },
    'C2_CANAL_DROUGHT': {
        'parent': 'C_WEATHER',
        'name': '운하 수위 부족 (El Niño)',
        'color': '#F57C00',
        'trigger': 'MRI ≥ 0.4 + 운하/수위/가뭄 키워드',
        'evidence': '2023 El Niño — 파나마운하 일일 통항 36→18척 제한, 평균 대기 7일',
        'delay_days': 7,
        'freight_surge_pct': 0.12,
        'affects_routes': ['부산→LA'],
        'cold_chain_priority': False,
    },
    # D 세분류 — 단순 지연 원인별
    'D1_PORT_STRIKE': {
        'parent': 'D_DELAY',
        'name': '항만 파업',
        'color': '#F9A825',
        'trigger': 'MRI 0.3~0.5 + 파업/노조 키워드',
        'evidence': '2023 독일 항만 파업 — 평균 3.2일 지연 (Destatis 2023)',
        'delay_days': 3,
        'freight_surge_pct': 0.02,
        'affects_routes': [],
    },
    'D2_TARIFF_DELAY': {
        'parent': 'D_DELAY',
        'name': '관세 통관 지연',
        'color': '#FBC02D',
        'trigger': 'MRI 0.3~0.5 + 관세/제재 키워드',
        'evidence': '2025.04 미국 관세 발효 후 LA항 통관 처리 평균 +2.3일 (USTR 추정)',
        'delay_days': 2,
        'freight_surge_pct': 0.05,
        'affects_routes': ['부산→LA'],
    },
    'D3_FREIGHT_SURGE': {
        'parent': 'D_DELAY',
        'name': '선복 부족·운임 급등',
        'color': '#FFD600',
        'trigger': 'MRI 0.3~0.5 + 운임급등/선복부족 키워드',
        'evidence': 'KCCI 2024 — 주간 상승률 5% 초과 시 선복 대기 평균 1.2일',
        'delay_days': 1,
        'freight_surge_pct': 0.10,
        'affects_routes': [],
    },
}

# ── 항로 정보 (실제 부산항 운임 기준) ─────────────────────────────────────────
ROUTE_INFO: Final[dict] = {
    '부산→상하이':   {'distance_nm': 485,   'usd_per_teu': 950,  'transit_days': 3},
    '부산→도쿄':    {'distance_nm': 610,   'usd_per_teu': 680,  'transit_days': 2},
    '부산→LA':      {'distance_nm': 5040,  'usd_per_teu': 2300, 'transit_days': 14},
    '부산→로테르담': {'distance_nm': 11200, 'usd_per_teu': 3500, 'transit_days': 28},
    '부산→싱가포르': {'distance_nm': 2650,  'usd_per_teu': 1050, 'transit_days': 7},
}

LCL_MULTIPLIER: Final[float] = 1.5  # LCL 단가 ≈ FCL × 1.5

# ── 화물 / 권역 상수 ──────────────────────────────────────────────────────────
REGIONS: Final[list[str]] = ['경기남부', '경기북부', '충청', '경상남부', '경상북부']
CARGO_TYPES: Final[list[str]] = ['일반화물', '냉장화물', '위험물']
CARGO_TYPE_PROBS: Final[list[float]] = [0.65, 0.25, 0.10]

# ── MRI AHP 가중치 (5차원 개선, 실데이터 근거 기반) ─────────────────────────
#
# [5대 리스크 차원]
# G (지정학·항로): 봉쇄·전쟁·항로 교란 — 운임 최대 100% 영향 (UNCTAD 2024)
# D (지연·운항):   출항 지연 일수 (14일 기준 정규화 — B1_RED_SEA 케이프타운 우회)
# F (운임 변동):   운임 변동률 (100% 상승 = 1.0 — 홍해 사태 피크 기준)
# V (통행량):      주요 해협 통행량 감소율 (50% 감소 = 1.0 — UNCTAD 수에즈 기준)
# P (항만·통상):   파업·관세·혼잡 (Destatis 2023 독일 항만 파업, USTR 2025)
#
# [쌍대비교 근거]
# G > D(3배): 봉쇄 자체가 지연보다 근본 원인
# G > F(2배): 지정학이 운임을 유발하나 F는 직접 경제 지표
# G > V(5배): 통행량은 사후 지표
# D ≈ F: 지연과 운임 상승은 동등한 운영 영향
# V > P: 통행량 감소는 광역, P는 개별 항만
#
# [검증] λ_max=5.140, CI=0.035, RI=1.12, CR=3.1% < 10% ✅
MRI_AHP_WEIGHTS: Final[dict] = {
    'G': 0.431,   # 지정학·항로 (봉쇄·전쟁 뉴스)
    'D': 0.182,   # 지연·운항 (지연 일수 / 14일)
    'F': 0.253,   # 운임 변동 (변동률 / 100%)
    'V': 0.090,   # 통행량 감소 (감소율 / 50%)
    'P': 0.044,   # 항만·통상 (파업·관세 뉴스)
}

# AHP 쌍대비교 행렬 [G, D, F, V, P] — Saaty 1~9 척도
# aij > 1: 행 요소가 열 요소보다 중요
MRI_AHP_MATRIX: Final[list] = [
    #   G       D       F       V       P
    [1,      3,      2,      5,      7   ],  # G: 지정학·항로
    [1/3,    1,      1/2,    3,      5   ],  # D: 지연·운항
    [1/2,    2,      1,      3,      5   ],  # F: 운임 변동
    [1/5,    1/3,    1/3,    1,      3   ],  # V: 통행량
    [1/7,    1/5,    1/5,    1/3,    1   ],  # P: 항만·통상
]

# MRI 등급 (하한 기준)
MRI_GRADES: Final[list[tuple]] = [
    (0.8, '🔴 위험',  '#EF5350'),
    (0.6, '🟠 경계',  '#FF7043'),
    (0.3, '🟡 주의',  '#FFA726'),
    (0.0, '🟢 정상',  '#66BB6A'),
]

# ── NLP 키워드 사전 (한글 + 영어 병기 — gCaptain·Splash247 등 영문 소스 대응) ──
RISK_KEYWORDS: Final[dict] = {
    '지정학분쟁': [
        # 한글
        '봉쇄', '전쟁', '분쟁', '공격', '테러', '후티', '이란', '러시아',
        '미사일', '충돌', '긴장', '갈등', '적대', '위협', '호르무즈', '홍해',
        # 영어
        'blockade', 'war', 'conflict', 'attack', 'terror', 'houthi', 'houthis',
        'iran', 'russia', 'missile', 'clash', 'tension', 'hostile', 'threat',
        'hormuz', 'red sea', 'strait', 'military', 'armed', 'seizure',
        'warship', 'naval', 'piracy', 'drone strike', 'sanctions',
    ],
    '항만파업': [
        # 한글
        '파업', '노조', '총파업', '시위', '거부', '협상', '체증', '하역', '부두',
        # 영어
        'strike', 'labor', 'labour', 'union', 'walkout', 'industrial action',
        'stoppage', 'dock', 'longshoremen', 'port congestion', 'gridlock',
        'workers', 'wage', 'dispute', 'picket',
    ],
    '기상재해': [
        # 한글
        '태풍', '폭풍', '가뭄', '홍수', '지진', '해일', '강풍', '기상',
        '이상기후', '운하', '수위', '결항',
        # 영어
        'typhoon', 'storm', 'drought', 'flood', 'earthquake', 'tsunami',
        'gale', 'weather', 'canal', 'water level', 'cyclone', 'el nino',
        'el niño', 'hurricane', 'monsoon', 'fog', 'ice', 'disruption',
    ],
    '관세정책': [
        # 한글
        '관세', '제재', '규제', '무역전쟁', 'IMO', '환경규제', '정책',
        '금지', '추가관세', '관세부과', 'CBAM',
        # 영어
        'tariff', 'sanction', 'regulation', 'trade war', 'IMO', 'CBAM',
        'embargo', 'ban', 'duty', 'customs', 'trade policy', 'levy',
        'protectionism', 'import restriction', 'carbon tax', 'CII',
    ],
    '운임급등': [
        # 한글
        '운임', '급등', '상승', 'SCFI', 'BDI', 'KCCI', '운임지수', '선복',
        '부족', '비용', '증가', '인상',
        # 영어
        'freight rate', 'SCFI', 'BDI', 'KCCI', 'freight index', 'surge',
        'capacity', 'shortage', 'rate hike', 'spot rate', 'bunker',
        'demurrage', 'congestion surcharge', 'peak season surcharge',
        'blank sailing', 'void sailing', 'GRI',
    ],
    '정상': [
        # 한글
        '정상화', '완화', '회복', '협력', '개설', '투자', '성장', '최대', '안정',
        # 영어
        'normalize', 'ease', 'recover', 'cooperation', 'investment',
        'growth', 'stable', 'record', 'resumption', 'relief', 'reopen',
    ],
}

RISK_WEIGHTS: Final[dict] = {
    '지정학분쟁': 1.0,
    '항만파업':   0.85,
    '기상재해':   0.75,
    '관세정책':   0.65,
    '운임급등':   0.55,
    '정상':       0.0,
}

NEG_WORDS: Final[list[str]] = [
    # 한글
    '봉쇄', '파업', '급등', '위협', '분쟁', '차질', '불안',
    '공격', '가뭄', '태풍', '관세', '제재', '인상', '악화',
    # 영어
    'blockade', 'strike', 'surge', 'threat', 'conflict', 'disruption',
    'attack', 'drought', 'typhoon', 'tariff', 'sanction', 'hike', 'deteriorate',
]
POS_WORDS: Final[list[str]] = [
    # 한글
    '정상화', '완화', '회복', '개설', '협력', '최대', '성장',
    # 영어
    'normalize', 'ease', 'recover', 'reopen', 'cooperation', 'record', 'growth',
]

# ── 권역 통합 절감률 ──────────────────────────────────────────────────────────
CONSOLIDATION_SAVINGS_RATE: Final[float] = 0.15  # 권역 통합 시 약 15% 절감

# ── 화물 호환성 (권역 통합 시 동일 타입끼리만 묶음) ──────────────────────────
CARGO_COMPAT: Final[set[tuple]] = {
    ('일반화물', '일반화물'),
    ('냉장화물', '냉장화물'),
    ('위험물',   '위험물'),
}
