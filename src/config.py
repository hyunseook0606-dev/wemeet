"""
config.py — 항로 정보, MRI 가중치 및 등급 상수
최종 확정: 2026-05-15 (위밋모빌리티 × KMI)
MRI 가중치: IQR 로버스트 엔트로피 + 등분 하이브리드 (AHP 완전 제거)
"""
from __future__ import annotations
from typing import Final

# ── 운영 리스크 시나리오 (Tab4 시뮬레이션 전용 — 화주 강제 적용 금지) ──────────
# 창고 보관 비용 시나리오(A/B/C)는 별도 scenario_cost.py 참조
SCENARIOS: Final[dict] = {
    'A_NORMAL': {
        'name': '평상시 운영',
        'icon': '🟢',
        'color': '#4CAF50',
        'trigger': 'MRI < 0.33 + 정상 카테고리',
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
        'trigger': 'MRI ≥ 0.55 + 지정학분쟁',
        'description': '항로 봉쇄·전쟁 위험. 케이프타운 우회 + 운임 +30% (실제 홍해 사태 사례).',
        'delay_days': 14,
        'freight_surge_pct': 0.30,
        'reroute_required': True,
        'cold_chain_priority': True,
        'affects_routes': ['부산→로테르담'],
        'policy': 'REROUTE_AND_HOLDBACK',
    },
    'C_WEATHER': {
        'name': '기상 악화 (태풍/폭풍)',
        'icon': '🟠',
        'color': '#F57C00',
        'trigger': 'MRI ≥ 0.43 + 기상재해',
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
        'trigger': 'MRI 0.33~0.43 + 파업/관세/운임급등',
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

# 세분화 서브 시나리오 (실제 뉴스 키워드·증거 기반)
# 출처: UNCTAD 연간 보고서, KMI 연구원, 실제 사례 데이터
SUB_SCENARIOS: Final[dict] = {
    # B 세분류 — 지정학 분쟁 유형별
    'B1_RED_SEA': {
        'parent': 'B_GEOPOLITICAL',
        'name': '홍해/수에즈 봉쇄',
        'color': '#C62828',
        'trigger': 'MRI >= 0.55 + 후티/홍해/수에즈 키워드',
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
        'trigger': 'MRI >= 0.55 + 이란/호르무즈 키워드',
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
        'trigger': 'MRI >= 0.43 + 미중/관세전쟁 키워드',
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
        'trigger': 'MRI >= 0.43 + 태풍/강풍 키워드 (6~9월)',
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
        'trigger': 'MRI >= 0.33 + 운하/수위/가뭄 키워드',
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
        'trigger': 'MRI 0.33~0.43 + 파업/노조 키워드',
        'evidence': '2023 독일 항만 파업 — 평균 3.2일 지연 (Destatis 2023)',
        'delay_days': 3,
        'freight_surge_pct': 0.02,
        'affects_routes': [],
    },
    'D2_TARIFF_DELAY': {
        'parent': 'D_DELAY',
        'name': '관세 통관 지연',
        'color': '#FBC02D',
        'trigger': 'MRI 0.33~0.43 + 관세/제재 키워드',
        'evidence': '2025.04 미국 관세 발효 후 LA항 통관 처리 평균 +2.3일 (USTR 추정)',
        'delay_days': 2,
        'freight_surge_pct': 0.05,
        'affects_routes': ['부산→LA'],
    },
    'D3_FREIGHT_SURGE': {
        'parent': 'D_DELAY',
        'name': '선복 부족·운임 급등',
        'color': '#FFD600',
        'trigger': 'MRI 0.33~0.43 + 운임급등/선복부족 키워드',
        'evidence': 'KCCI 2024 — 주간 상승률 5% 초과 시 선복 대기 평균 1.2일',
        'delay_days': 1,
        'freight_surge_pct': 0.10,
        'affects_routes': [],
    },
}

# ── 항로 정보 (실제 부산항 출발 운임 기준) ───────────────────────────────────
ROUTE_INFO: Final[dict] = {
    '부산→상하이':    {'distance_nm': 485,   'usd_per_teu': 950,  'transit_days': 3},
    '부산→도쿄':     {'distance_nm': 610,   'usd_per_teu': 680,  'transit_days': 2},
    '부산→LA':       {'distance_nm': 5040,  'usd_per_teu': 2300, 'transit_days': 14},
    '부산→로테르담':  {'distance_nm': 11200, 'usd_per_teu': 3500, 'transit_days': 28},
    '부산→싱가포르':  {'distance_nm': 2650,  'usd_per_teu': 1050, 'transit_days': 7},
}

LCL_MULTIPLIER: Final[float] = 1.5  # LCL 소량 화물 FCL 대비 1.5배

# ── 권역 / 화물유형 목록 ──────────────────────────────────────────────────────
REGIONS: Final[list[str]] = ['경기남부', '경기북부', '충청', '경상남부', '경상북부']
CARGO_TYPES: Final[list[str]] = ['일반화물', '냉장화물', '위험물']
CARGO_TYPE_PROBS: Final[list[float]] = [0.65, 0.25, 0.10]

# ── MRI 가중치 (IQR 로버스트 엔트로피 + 등분 하이브리드) ────────────────────
# 역사 기간: 2015-02 ~ 2026-05 (136개월, GDELT v2 시작일 기준)
# 산출: IQR Tukey 클리핑 → Shannon 엔트로피 가중치 vs 등분(0.2) → 단순 평균
# 웹앱(app.py) 실시간 계산과 노트북 역사 시계열 모두 동일 가중치 사용
MRI_WEIGHTS: Final[dict] = {
    'G': 0.132,   # 지정학·항로
    'D': 0.132,   # 운항방해·부정감성
    'F': 0.183,   # 운임 변동
    'V': 0.437,   # 물동량 (BPA YoY + LSTM)
    'P': 0.115,   # 항만·통상
}

# 하위 호환성 — 기존 코드가 MRI_AHP_WEIGHTS를 참조할 경우 동일 값 반환
MRI_AHP_WEIGHTS: Final[dict] = MRI_WEIGHTS

# MRI 등급 (하한 기준)
# [설계 근거: 2015-02~2026-05 실데이터 136개월 분위수 + Jenks 자연 구간 검증]
#   0.33 = 75th 퍼센타일 — 홍해 위기 정점(0.333)이 주의 진입
#   0.43 = 91th 퍼센타일 — Jenks 최대 갭(0.431→0.479) 직전
#   0.55 = 95th 퍼센타일 — 수에즈 에버기븐(0.593)·COVID(0.656)만 위험 진입
MRI_GRADES: Final[list[tuple]] = [
    (0.55, '🔴 위험',  '#EF5350'),
    (0.43, '🟠 경계',  '#FF7043'),
    (0.33, '🟡 주의',  '#FFA726'),
    (0.00, '🟢 정상',  '#66BB6A'),
]

# ── NLP 키워드 사전 (한글 + 영어 병기 — gCaptain·Splash247 등 영문 소스 대응) ──
RISK_KEYWORDS: Final[dict] = {
    '지정학분쟁': [
        # 한글
        '전쟁', '분쟁', '갈등', '공격', '폭격', '후티', '이란', '러시아',
        '미사일', '충돌', '긴장', '봉쇄', '점령', '나포', '호르무즈', '홍해',
        # 영어
        'blockade', 'war', 'conflict', 'attack', 'terror', 'houthi', 'houthis',
        'iran', 'russia', 'missile', 'clash', 'tension', 'hostile', 'threat',
        'hormuz', 'red sea', 'strait', 'military', 'armed', 'seizure',
        'warship', 'naval', 'piracy', 'drone strike', 'sanctions',
    ],
    '항만파업': [
        # 한글
        '파업', '노조', '쟁의행위', '집회', '봉쇄', '혼잡', '혼잡도', '항만',
        # 영어
        'strike', 'labor', 'labour', 'union', 'walkout', 'industrial action',
        'stoppage', 'dock', 'longshoremen', 'port congestion', 'gridlock',
        'workers', 'wage', 'dispute', 'picket',
    ],
    '기상재해': [
        # 한글
        '태풍', '폭풍', '가뭄', '홍수', '지진', '해일', '강풍', '기상',
        '기상악화', '운하', '수위', '결항',
        # 영어
        'typhoon', 'storm', 'drought', 'flood', 'earthquake', 'tsunami',
        'gale', 'weather', 'canal', 'water level', 'cyclone', 'el nino',
        'el niño', 'hurricane', 'monsoon', 'fog', 'ice', 'disruption',
    ],
    '관세정책': [
        # 한글
        '관세', '제재', '규제', '통상규제', 'IMO', '국제규제', '탄소',
        '탄소세', '이중과세', '보복관세', 'CBAM',
        # 영어
        'tariff', 'sanction', 'regulation', 'trade war', 'IMO', 'CBAM',
        'embargo', 'ban', 'duty', 'customs', 'trade policy', 'levy',
        'protectionism', 'import restriction', 'carbon tax', 'CII',
    ],
    '운임급등': [
        # 한글
        '운임', '급등', '상승', 'SCFI', 'BDI', 'KCCI', '운임지수', '선복',
        '부족', '용선', '인상', '증가',
        # 영어
        'freight rate', 'SCFI', 'BDI', 'KCCI', 'freight index', 'surge',
        'capacity', 'shortage', 'rate hike', 'spot rate', 'bunker',
        'demurrage', 'congestion surcharge', 'peak season surcharge',
        'blank sailing', 'void sailing', 'GRI',
    ],
    '정상': [
        # 한글
        '정상화', '안정', '회복', '협력', '투자', '증가', '개선', '합의', '타결',
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
    '전쟁', '파업', '급등', '봉쇄', '갈등', '지연', '결항',
    '공격', '가뭄', '태풍', '관세', '제재', '인상', '악화',
    # 영어
    'blockade', 'strike', 'surge', 'threat', 'conflict', 'disruption',
    'attack', 'drought', 'typhoon', 'tariff', 'sanction', 'hike', 'deteriorate',
]
POS_WORDS: Final[list[str]] = [
    # 한글
    '정상화', '안정', '회복', '협력', '합의', '개선', '증가',
    # 영어
    'normalize', 'ease', 'recover', 'cooperation', 'agreement',
    'growth', 'stable', 'resumption', 'relief',
]
