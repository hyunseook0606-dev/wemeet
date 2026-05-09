# 프로젝트 상세 명세 (PROJECT_SPEC)

> Claude Code가 코드 생성 시 참조할 상세 명세서.
> 이 문서의 모든 수치·구조는 **이미 검증된 값**이므로 임의 변경 금지.

---

## 1. 시나리오 파라미터 (절대 변경 금지)

### 1.1 시나리오 정의 (Python dict 형식)

```python
SCENARIOS = {
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
        'affects_routes': [],          # 빈 리스트 = 영향 없음
        'policy': 'AS_PLANNED',
    },
    'B_GEOPOLITICAL': {
        'name': '지정학 분쟁 (호르무즈/홍해)',
        'icon': '🔴',
        'color': '#D32F2F',
        'trigger': 'MRI ≥ 0.7 + 지정학분쟁',
        'description': '항로 봉쇄·전쟁 위험. 케이프타운 우회 + 운임 +30% (실제 홍해 사태 사례).',
        'delay_days': 14,              # 케이프타운 우회 실제 소요
        'freight_surge_pct': 0.30,     # 2023~2024 홍해 사태 실제 +30%
        'reroute_required': True,
        'cold_chain_priority': True,
        'affects_routes': ['부산→로테르담'],  # 수에즈 경유 항로만
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
        'affects_routes': [],          # 전체 항로 영향
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
```

### 1.2 자동 분류 규칙

```python
def auto_classify_scenario(today_mri: float,
                            top_category: str,
                            cancel_count: int = 0) -> str:
    """
    우선순위:
    1. 취소 발생 → E_CANCELLATION (최우선)
    2. 카테고리 + MRI 매칭 (구체적 → 일반적)
    3. 카테고리 불명확 시 MRI 점수만으로 fallback
    """
    if cancel_count > 0:
        return 'E_CANCELLATION'

    if top_category == '지정학분쟁' and today_mri >= 0.7:
        return 'B_GEOPOLITICAL'
    if top_category == '기상재해' and today_mri >= 0.5:
        return 'C_WEATHER'
    if top_category in ['항만파업', '관세정책', '운임급등'] and today_mri >= 0.3:
        return 'D_DELAY'
    if today_mri < 0.3:
        return 'A_NORMAL'

    # MRI fallback
    if today_mri >= 0.7: return 'B_GEOPOLITICAL'
    if today_mri >= 0.5: return 'C_WEATHER'
    if today_mri >= 0.3: return 'D_DELAY'
    return 'A_NORMAL'
```

---

## 2. 데이터 구조 (Dataclass)

### 2.1 ShipmentRequest (출하 예정 건)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ShipmentRequest:
    shipment_id: str          # 'SH-001'
    company: str              # '화주_A'
    route: str                # '부산→LA' (ROUTE_INFO의 키와 일치)
    cargo_type: str           # '일반화물' / '냉장화물' / '위험물'
    region: str               # '경기남부' / '경기북부' / '충청' / '경상남부' / '경상북부'
    pickup_date: datetime     # 집화 예정일
    cbm: float                # 화물 부피 (5~35 범위)
    deadline_days: int        # 납기 허용 일수 (7/10/14/21)
    urgent: bool              # 긴급 화물 여부
    estimated_cost: int       # 예상 운임 (USD)
```

### 2.2 ImpactAnalysis (영향 분석 결과)

```python
@dataclass
class ImpactAnalysis:
    shipment_id: str
    is_affected: bool          # 시나리오 영향 여부
    delay_days_applied: int    # 적용된 지연일
    new_pickup_date: datetime  # 조정된 집화일
    new_estimated_cost: int    # 조정된 운임
    cost_delta: int            # 운임 변화 (음수=절감)
    deadline_violated: bool    # 납기 초과 위험
    requires_holdback: bool    # 항만 반입 보류 필요
    requires_priority: bool    # 우선처리 필요
    reason: str                # 사람이 읽는 이유 설명
```

### 2.3 ConsolidationGroup (권역 통합 그룹)

```python
@dataclass
class ConsolidationGroup:
    region: str                  # '경기남부'
    cargo_type: str              # '냉장화물' (호환되는 화물끼리만)
    merged_pickup_date: str      # 'YYYY-MM-DD'
    members: list[str]           # ['SH-001', 'SH-007']
    companies: list[str]         # ['화주_A', '화주_G']
    total_cbm: float
    savings_estimate_pct: float  # 0.15 (권역 통합 시 약 15% 절감)
```

---

## 3. 운영 재조정 정책 (4가지 행동)

### 3.1 행동 분류 규칙

```python
# 우선순위: PRIORITY > HOLDBACK > SHIFT
if requires_priority:
    action = 'PRIORITY'    # 콜드체인 + cold_chain_priority 시나리오 OR 긴급 화물
elif requires_holdback:
    action = 'HOLDBACK'    # delay_days >= 3 AND not urgent
else:
    action = 'SHIFT'       # 단순 일정 이동
```

### 3.2 권역 통합 매칭 규칙

```python
# 통합 조건 (모두 충족):
# 1. 같은 region
# 2. 같은 cargo_type (호환성: 일반↔일반, 냉장↔냉장, 위험↔위험)
# 3. 새 집화일 ±2일 이내
# 4. 그룹당 최소 2건 이상

# 절감 추정: 권역 통합 시 약 15%
SAVINGS_RATE = 0.15
```

---

## 4. 항로 정보 (실제 부산항 운임 기준)

```python
ROUTE_INFO = {
    '부산→상하이':  {'distance_nm': 485,   'usd_per_teu': 950,   'transit_days': 3},
    '부산→도쿄':    {'distance_nm': 610,   'usd_per_teu': 680,   'transit_days': 2},
    '부산→LA':      {'distance_nm': 5040,  'usd_per_teu': 2300,  'transit_days': 14},
    '부산→로테르담': {'distance_nm': 11200, 'usd_per_teu': 3500,  'transit_days': 28},
    '부산→싱가포르': {'distance_nm': 2650,  'usd_per_teu': 1050,  'transit_days': 7},
}

# LCL 운임 = (CBM / 33) × USD_per_TEU × 1.5  (LCL 단가 1.5배 보정)
LCL_MULTIPLIER = 1.5

def calc_freight(cbm: float, route: str) -> int:
    info = ROUTE_INFO[route]
    fcl_per_cbm = info['usd_per_teu'] / 33
    return round(fcl_per_cbm * LCL_MULTIPLIER * cbm)
```

---

## 5. 루티 API JSON 표준 출력

### 5.1 JSON 스키마

```json
{
  "execution_group_id": "EG-YYYYMMDD-{SCENARIO_ID}",
  "generated_at": "ISO8601 형식 timestamp",
  "scenario": {
    "id": "B_GEOPOLITICAL",
    "name": "지정학 분쟁 (호르무즈/홍해)",
    "icon": "🔴",
    "policy": "REROUTE_AND_HOLDBACK",
    "description": "..."
  },
  "summary": {
    "total_shipments": 30,
    "affected": 11,
    "priority": 2,
    "holdback": 9,
    "shifted": 0,
    "consolidation_groups": 0,
    "total_cost_delta_usd": 9338,
    "deadline_violations": 4
  },
  "pickup_adjustments": [
    {
      "shipment_id": "SH-001",
      "company": "화주_A",
      "region": "경기남부",
      "cbm": 23.0,
      "cargo_type": "위험물",
      "route": "부산→로테르담",
      "original_pickup": "2026-05-10",
      "adjusted_pickup": "2026-05-24",
      "action": "HOLDBACK",
      "cost_delta_usd": 1098,
      "deadline_violated": true,
      "cold_chain": false
    }
  ],
  "consolidation_groups": [
    {
      "region": "경기남부",
      "cargo_type": "냉장화물",
      "merged_pickup_date": "2026-05-18",
      "members": ["SH-007", "SH-012"],
      "companies": ["화주_G", "화주_L"],
      "total_cbm": 17.5,
      "savings_estimate_pct": 0.15
    }
  ],
  "priority_routing": ["SH-003"],
  "holdback_list": ["SH-001", "SH-005"],
  "cargo_special_handling": {
    "cold_chain_count": 8,
    "hazardous_count": 3
  },
  "meta": {
    "note": "본 출력은 위밋 루티/루티프로 API 입력 스펙으로 설계됨",
    "integration_status": "simulation_mode",
    "next_step_api": "POST /v1/dispatch/execute"
  }
}
```

### 5.2 파일명 규칙
- 저장 경로: `routy_inputs/EG-{YYYYMMDD}-{SCENARIO_ID}.json`
- 예: `routy_inputs/EG-20260512-B_GEOPOLITICAL.json`

---

## 6. MRI (Maritime Risk Index) 산출 공식

### 6.1 가중치 (신청서와 일치, 변경 금지)

```python
MRI = 0.40 × neg_news_ratio        # 부정 뉴스 비율 [0~1]
    + 0.30 × event_count_norm       # 이벤트 빈도 정규화 [0~1]
    + 0.20 × freight_change_norm    # 운임 변동률 정규화 [0~1]
    + 0.10 × high_risk_norm         # 고위험 비율 [0~1]
```

### 6.2 등급 분류

```python
def mri_grade(mri: float) -> tuple[str, str]:
    if mri >= 0.8: return ('🔴 위험',  '#EF5350')
    if mri >= 0.6: return ('🟠 경계',  '#FF7043')
    if mri >= 0.3: return ('🟡 주의',  '#FFA726')
    return               ('🟢 정상',  '#66BB6A')
```

---

## 7. NLP 카테고리 분류 (키워드 사전)

### 7.1 6개 카테고리 + 키워드

```python
RISK_KEYWORDS = {
    '지정학분쟁': ['봉쇄', '전쟁', '분쟁', '공격', '테러', '후티', '이란', '러시아',
                   '미사일', '충돌', '긴장', '갈등', '적대', '위협', '호르무즈', '홍해'],
    '항만파업':   ['파업', '파멸', '노조', '총파업', '시위', '불법', '거부',
                   '협상', '체증', '하역', '부두'],
    '기상재해':   ['태풍', '폭풍', '가뭄', '홍수', '지진', '해일', '강풍', '기상',
                   '이상기후', '운하', '수위', '결항'],
    '관세정책':   ['관세', '제재', '규제', '무역전쟁', 'IMO', '환경규제', '정책',
                   '금지', '추가관세', '관세부과', 'CBAM'],
    '운임급등':   ['운임', '급등', '상승', 'SCFI', 'BDI', 'KCCI', '운임지수', '선복',
                   '부족', '비용', '증가', '인상'],
    '정상':       ['정상화', '완화', '회복', '협력', '개설', '투자',
                   '성장', '최대', '안정'],
}

RISK_WEIGHTS = {
    '지정학분쟁': 1.0,
    '항만파업':   0.85,
    '기상재해':   0.75,
    '관세정책':   0.65,
    '운임급등':   0.55,
    '정상':       0.0,
}
```

### 7.2 감성 판정 (규칙 기반)

```python
neg_words = ['봉쇄', '파업', '급등', '위협', '분쟁', '차질', '불안',
             '공격', '가뭄', '태풍', '관세', '제재', '인상', '악화']
pos_words = ['정상화', '완화', '회복', '개설', '협력', '최대', '성장']
```

---

## 8. LSTM 물동량 예측 (시간순 분할 필수)

### 8.1 하이퍼파라미터

```python
FEATURES = ['throughput', 'gdp_growth', 'exchange_rate', 'oil_price', 'mri']
TARGET = 'throughput'
LOOKBACK = 12   # 과거 12개월 → 3개월 예측
HORIZON = 3

# 모델 구조
class LSTMModel(nn.Module):
    def __init__(self, in_dim=5, hidden=64, layers=2, horizon=3):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, layers, dropout=0.2, batch_first=True)
        self.fc = nn.Sequential(
            nn.Linear(hidden, 32), nn.ReLU(),
            nn.Dropout(0.2), nn.Linear(32, horizon)
        )
```

### 8.2 시간순 분할 (★ data leakage 방지)

```python
# ❌ 절대 금지
# train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])

# ✅ 시간순 슬라이싱 필수
train_size = int(len(dataset) * 0.80)
train_ds = torch.utils.data.Subset(dataset, list(range(train_size)))
val_ds   = torch.utils.data.Subset(dataset, list(range(train_size, len(dataset))))

# 검증은 셔플 안 함 (시간순 평가)
val_loader = DataLoader(val_ds, batch_size=16, shuffle=False)
```

---

## 9. 실데이터 소스 (1차 자료)

### 9.1 KCCI (한국형 컨테이너 운임지수, 1순위)

- **공식 출처**: 한국해양진흥공사(KOBC), 매주 월요일 14시 발표
- **다운로드**:
  - 공공데이터포털: https://www.data.go.kr/data/15131881
  - Forwarder.kr (간편): https://www.forwarder.kr/freight/index/kcci
- **저장 위치**: `data/kcci.csv`
- **컬럼 자동 감지**: 날짜 컬럼 (`발표일`/`일자`/`기준`), 값 컬럼 (`KCCI`/`종합지수`)

### 9.2 부산항 컨테이너 물동량

- **부산항만공사 BPA**: https://www.busanpa.com/kor/Contents.do?mCode=MN1003
  - 신항/북항 분리 데이터 (천 TEU 단위)
- **국가물류통합정보센터**: https://www.nlic.go.kr/nlic/seaHarborGtqy.action
- **저장 위치**: `data/busan_throughput.csv`
- **단위 변환**: TEU → 만 TEU (자동 감지)

### 9.3 한국은행 ECOS API

- **API 엔드포인트**: https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/xml/kr/...
- **인증키 발급**: https://ecos.bok.or.kr/api/ → 회원가입 즉시
- **통계코드**:
  - 환율(원/달러): `731Y001`/`0000001`
  - 두바이유: `902Y020`/`I61BCS`
  - GDP: `200Y001`/`*`
- **캐시**: `data/ecos_cache/{stat_code}_{item_code}_{start}_{end}.csv`
- **환경변수**: `ECOS_API_KEY`

---

## 10. 발표 시 인용 가능한 1차 자료

### 10.1 위밋모빌리티 자산 (출처 확보)
- 루티(ROOUTY): 1억 건 이상 실주행 데이터 학습
- 도입 효과: 차량 투입 28% 감소(월 1.97억 절감), 평균 이동시간 11.8% 감소
- 트렌드 리포트 (2025): "해외에서 시작해 국내운송의 일정과 비용으로 전이되는 구조"
- 중소기업 기술마켓 등록 (2026.01.19)
- 인천대 동북아물류대학원 산학협력 MOU (2026.01.30)

### 10.2 트레드링스 (비교 대상, 사실만 인용)
- 6만여 수출입 기업, 160만 회원, 글로벌 3,000개사 도입
- ShipGo 평균 99.5% 추적 정확도
- End-to-End 가시성 (단, 항만 도착까지)
- 2025.11 디머리지&디텐션 모니터링 추가
- LinGo는 화주↔포워더 매칭 (화주↔화주 공동선적 아님)

### 10.3 EU CBAM (ESG 모듈용, 향후 확장)
- 한국 대EU 수출 51억 달러 영향권 (법무부 보고서)
- 중소기업 78.3% CBAM 미인지 (중소기업중앙회 2023.09 조사)
- 2026.01.01 본격 시행, 2027.02 인증서 판매 시작
- 위밋 플랫폼 ESG 모듈 절감률 35% (적재율 55→85% 가정)

---

## 11. 필수 검증 체크리스트

코드 작성 후 다음 항목 모두 OK여야 함:

### 11.1 정확성
- [ ] 부산항 평균 물동량이 200만 TEU 근처 (실제 2024년 평균 203만)
- [ ] 운임 방향성 정확도가 30~70% 범위 (자기참조 없는 정직한 측정)
- [ ] LSTM 학습/검증 분할이 시간순임 (시작 인덱스 < 끝 인덱스)

### 11.2 시나리오 동작
- [ ] A 시나리오: 영향 0건, 비용 변화 0
- [ ] B 시나리오: 부산→로테르담만 영향, +30% 운임
- [ ] C 시나리오: 전체 영향, 콜드체인 우선처리
- [ ] D 시나리오: 전체 영향, +3일 지연
- [ ] E 시나리오: 취소된 건만 처리

### 11.3 JSON 출력
- [ ] `execution_group_id` 형식 일치
- [ ] `meta.integration_status = 'simulation_mode'`
- [ ] 파일이 `routy_inputs/`에 저장됨

### 11.4 발표 준비
- [ ] 호르무즈 케이스 스터디 코드 동작
- [ ] 5개 시나리오 일괄 실행 가능
- [ ] KPI 시각화 (matplotlib + plotly) 정상 출력
