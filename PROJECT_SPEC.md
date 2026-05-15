# 프로젝트 상세 명세 (PROJECT_SPEC)

> Claude Code가 코드 생성 시 참조할 상세 명세서.
> 이 문서의 모든 수치·구조는 **이미 검증된 값**이므로 임의 변경 금지.
> 최종 확정: 2026-05-15 (위밋모빌리티 × KMI)

---

## 플랫폼 개요

**해상 리스크 대응형 공동 물류 운영 플랫폼**

화주가 해상 리스크를 선제적으로 파악하고, 창고 보관 옵션을 직접 비교하여 최적 의사결정을 내릴 수 있도록 지원. 플랫폼은 **정보 제시**만 담당하며 화주 행동을 강제하지 않는다.

---

## 핵심 설계 원칙

- **강제 시나리오 없음**: MRI 등급에 무관하게 창고 추천 제공. 화주가 직접 결정.
- `build_risk_context()` → 화주 제시용 리스크 맥락 (과거 유사사례 평균 기반)
- `estimate_impact_advisory()` → 참고 추정값 (확정값 아님, 화주 결정 지원용)
- 루티(ROOUTY) Phase 1 JSON만 생성. Phase 2는 화주가 선적 재개 시점 결정 후 별도 진행.

---

## 0. 플랫폼 4단계 흐름

```
Step 1  화주 입력     화물종류·CBM·항로·납기·집화일·현재운임 → SHIPPER_INPUT dict
Step 2  MRI + 맥락   실데이터(SCFI/CCFI/KCCI/BPA/GDELT/Naver) → IQR 엔트로피+등분 가중치
                      MRI 등급 판정 / LSTM 3개월 예측 / 실시간 해사뉴스 피드
                      과거 유사사례(historical_matcher) 평균 지연·운임 참고 제시
Step 3  창고 추천     NLIC DB(439개) → 거리 기준 5곳 추천 (MRI 등급 무관, 모든 화주)
                      화주 직접 전화문의 후 일일 보관료 입력
                      시나리오 A/B/C 비용 자동 계산 및 차트 비교
Step 4  루티 JSON     Phase 1 (출발지→보세창고) JSON 생성만
                      Phase 2(창고→CY)는 화주 요청 시 별도 운송 지시
```

---

## 1. 시나리오 정의 (창고 보관 비용 비교용 — 화주 의사결정 지원)

> 이 시나리오는 **항만 도착 후 선적 지연 시 보관 비용 비교** 목적.
> 기존 A_NORMAL/B_GEOPOLITICAL 등 운영 시나리오와 별개.

### 1.1 단가 기준 (2024년 부산항 주변 업체 확인치)

```python
CY_FREE_DAYS        = 5          # CY 무료 장치기간 (일)
ODCY_DAILY_KRW      = 10_000    # ODCY 보관료 (원/CBM/일)
BONDED_DAILY_KRW    = 4_000     # 외부 보세창고 보관료 (원/CBM/일)
CY_DEMURRAGE_KRW    = 30_000    # CY 초과 장치료 Demurrage (원/CBM/일)
ODCY_TRANSFER_KRW   = 150_000   # CY→ODCY 이송비 (원/건 고정)
BONDED_TRANSFER_KRW = 100_000   # 출발지→보세창고 추가 이송비 (원/건 고정)
```

### 1.2 시나리오 A — 무대응 → CY 반입 → ODCY 이송

```
CY 반입 → 무료 5일 소진 → ODCY 이송
비용 = (delay_days - 5) × CBM × 10,000 + 이송비 150,000원
```

### 1.3 시나리오 B — 무대응 → CY 반입 → ODCY 만석 → CY 계속 장치

```
CY 반입 → 무료 5일 소진 → ODCY 자리 없어 CY 계속 장치
비용 = (delay_days - 5) × CBM × 30,000  (Demurrage, 가장 비쌈)
```

### 1.4 시나리오 C ★ — 플랫폼 탐지 → 외부 보세창고 선이송 (권장)

```
MRI 이상 탐지 → 출발지에서 직접 보세창고로 선이송 (CY 미반입)
비용 = delay_days × CBM × 4,000 + 이송비 100,000원  (가장 저렴)
```

### 1.5 시뮬레이션 예시 (CBM=15, 지연=14일)

| 시나리오 | 보관료 | 이송비 | 합계 | A 대비 |
|---|---|---|---|---|
| A — ODCY 이송 | 1,350,000원 | 150,000원 | 1,500,000원 | 기준 |
| B — CY 장치 | 4,050,000원 | 0원 | 4,050,000원 | +2,550,000원↑ |
| C ★ — 보세창고 | 840,000원 | 100,000원 | 940,000원 | -560,000원↓ |

※ C안이 A안 대비 37% 저렴, B안 대비 77% 저렴. 지연일이 길수록 격차 증가.

---

## 2. MRI (Maritime Risk Index) 산출 공식

### 2.1 5차원 정의 및 데이터 소스

| 차원 | 의미 | 데이터 소스 | 하이브리드 가중치 |
|---|---|---|---|
| G | 지정학·항로 | GDELT BigQuery + Naver DataLab (80:20) | 0.132 |
| D | 운항방해·부정감성 | GDELT Tone + Naver DataLab (80:20) | 0.132 |
| F | 운임 변동 | SCFI/CCFI(~2022-10) + KCCI(2022-11~) 월변화율 | 0.183 |
| V | 물동량 | BPA 부산항 12개월 롤링 YoY + LSTM 예측 | 0.437 |
| P | 항만·통상 | GDELT 제재이벤트 + Naver DataLab (80:20) | 0.115 |

```python
MRI = 0.132·G + 0.132·D + 0.183·F + 0.437·V + 0.115·P
```

### 2.2 가중치 산출 방법론 (IQR 로버스트 엔트로피 + 등분 하이브리드)

- **IQR 로버스트 엔트로피 (Shannon 1948 + Tukey 1977)**
  - COVID 같은 이상치는 IQR 울타리(Q1-1.5×IQR, Q3+1.5×IQR)로 클리핑
  - 클리핑 후 Min-Max 정규화 → Shannon 엔트로피 → 가중치
  - 변동이 많은 차원 = 정보량 많음 = 높은 가중치
- **등분 가중치(0.2×5)와 평균 (다중공선성 보정)**
  - G·D·F·V·P는 독립적이지 않음 (전쟁 → G·D·F 동시 상승)
  - 순수 엔트로피만 사용 시 V가 0.675로 과대 가중 → 등분 평균으로 보정

```
역사 기간: 2015-02 ~ 2026-05 (GDELT v2 시작일 기준)
```

### 2.3 MRI 등급 임계값 (분위수 기반, 실데이터 136개월)

```python
MRI_GRADES = [
    (0.55, '🔴 위험',  '#EF5350'),   # 상위 5%  — 수에즈 에버기븐(0.65), COVID(0.69)
    (0.43, '🟠 경계',  '#FF7043'),   # 91~95th  — 복합 위기
    (0.33, '🟡 주의',  '#FFA726'),   # 75~91th  — 홍해 위기 정점(0.39)
    (0.00, '🟢 정상',  '#66BB6A'),   # ~75th    — 미중 관세전쟁(0.20), 러우전쟁(0.21)
]
```

---

## 3. 데이터 구조 (Dataclass)

### 3.1 ShipmentRequest (화주 입력)

```python
@dataclass
class ShipmentRequest:
    shipment_id:     str        # 'SH-001'
    company:         str        # '화주_A'
    cargo_type:      str        # '일반화물' / '냉장화물' / '냉동화물' / '위험물' 등
    region:          str        # '경기남부' 등 (출발지 권역)
    pickup_date:     datetime   # 집화 예정일
    cbm:             float      # 화물 부피
    route:           str        # '부산→LA' 등
    deadline_days:   int        # 납기 허용 일수
    current_freight: int        # 현재 해상 운임 (USD)
```

### 3.2 RiskContext (화주 제시용 리스크 맥락)

```python
@dataclass
class RiskContext:
    mri:                      float
    grade:                    str            # '정상' / '주의' / '경계' / '위험'
    grade_color:              str
    top_category:             str            # NLP 분류 최다 카테고리
    current_issue:            str            # 뉴스 키워드 기반 한줄 요약
    top_keywords:             list[str]
    similar_events:           list[dict]     # historical_matcher 결과 (top 3)
    avg_delay_days:           float          # 유사사례 평균 지연일
    avg_freight_change_pct:   float
    warehouse_recommended:    bool           # 항상 True (모든 고객 이용 가능)
    advisory_note:            str            # 화주 제시 참고 문구
```

### 3.3 ScenarioCost (비용 명세 — scenario_cost.py)

```python
@dataclass
class ScenarioCost:
    label:          str     # 'A', 'B', 'C'
    name:           str
    storage_krw:    int     # 보관료 합계
    transfer_krw:   int     # 이송비
    total_krw:      int     # 합계
    recommend:      bool    # C안만 True
    note:           str
```

---

## 4. 항로 정보 (실제 부산항 운임 기준)

```python
ROUTE_INFO = {
    '부산→상하이':   {'distance_nm': 485,   'usd_per_teu': 950,  'transit_days': 3},
    '부산→도쿄':    {'distance_nm': 610,   'usd_per_teu': 680,  'transit_days': 2},
    '부산→LA':      {'distance_nm': 5040,  'usd_per_teu': 2300, 'transit_days': 14},
    '부산→로테르담': {'distance_nm': 11200, 'usd_per_teu': 3500, 'transit_days': 28},
    '부산→싱가포르': {'distance_nm': 2650,  'usd_per_teu': 1050, 'transit_days': 7},
}
LCL_MULTIPLIER = 1.5   # LCL 단가 = FCL 대비 1.5배
```

---

## 5. 루티 API JSON 표준 출력 (Phase 1 전용)

### 5.1 JSON 스키마

```json
{
  "execution_group_id": "EG-YYYYMMDD-PHASE1",
  "generated_at": "ISO8601 timestamp",
  "phase": "PHASE1_TO_STORAGE",
  "risk_context": {
    "mri": 0.48,
    "grade": "🟠 경계",
    "delay_reason": "홍해 위기 — 운임 상승 감지"
  },
  "shipment": {
    "cargo_type": "일반화물",
    "cbm": 15.0,
    "cold_chain": false,
    "hazmat": false
  },
  "dispatch": {
    "origin": {
      "address": "경기도 화성시 ...",
      "region": "경기남부"
    },
    "destination": {
      "name": "추천 보세창고명",
      "address": "부산광역시 ...",
      "phone": "051-000-0000",
      "distance_km": 12.5,
      "duration_min": 45
    }
  },
  "meta": {
    "note": "Phase 2(창고→CY)는 화주가 선적 재개 시점 결정 후 별도 운송 지시",
    "integration_status": "simulation_mode",
    "next_step_api": "POST /v1/dispatch/execute"
  }
}
```

### 5.2 파일명 규칙

- 저장 경로: `routy_inputs/EG-{YYYYMMDD}-PHASE1.json`

---

## 6. LSTM 물동량 예측

### 6.1 하이퍼파라미터

```python
FEATURES = ['throughput', 'gdp_growth', 'exchange_rate', 'oil_price', 'mri']
TARGET   = 'throughput'
LOOKBACK = 12   # 과거 12개월 → 3개월 예측
HORIZON  = 3

class LSTMModel(nn.Module):
    def __init__(self, in_dim=5, hidden=64, layers=2, horizon=3):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, layers, dropout=0.2, batch_first=True)
        self.fc   = nn.Sequential(
            nn.Linear(hidden, 32), nn.ReLU(),
            nn.Dropout(0.2), nn.Linear(32, horizon)
        )
```

### 6.2 시간순 분할 (★ data leakage 방지)

```python
# ❌ 절대 금지
# train_ds, val_ds = random_split(dataset, [...])

# ✅ 시간순 슬라이싱
train_size = int(len(dataset) * 0.80)
train_ds   = Subset(dataset, list(range(train_size)))
val_ds     = Subset(dataset, list(range(train_size, len(dataset))))
val_loader = DataLoader(val_ds, batch_size=16, shuffle=False)
```

- LSTM MAPE: **9.4%** (원단위 역정규화 후 계산, 시간순 분할 기준)

---

## 7. 창고 탐색 우선순위

```
1순위: NLIC 국가물류통합정보센터 DB — data/nlic_warehouses.json (439개, 좌표 포함)
2순위: 카카오 Local API — 항만 반경 15km 실시간 검색
3순위: 내장 시뮬 DB — NLIC JSON 없을 때만 폴백 (9개 대표 창고)
```

- NLIC 있으면 `simulation_mode = False` (정부 실데이터)
- MRI 등급에 **무관**하게 모든 화주에게 제공
- 거리 기준 5곳 추천 → 화주 직접 전화문의 → 일일 보관료 직접 입력

---

## 8. NLP 카테고리 분류

### 8.1 6개 카테고리

```python
RISK_KEYWORDS = {
    '지정학분쟁': ['봉쇄', '전쟁', '후티', '이란', '호르무즈', '홍해', 'blockade', 'houthi', ...],
    '항만파업':   ['파업', '노조', '혼잡', 'strike', 'union', ...],
    '기상재해':   ['태풍', '폭풍', '가뭄', '운하', '수위', 'typhoon', 'canal', ...],
    '관세정책':   ['관세', '제재', 'IMO', 'CBAM', 'tariff', 'sanction', ...],
    '운임급등':   ['운임', '급등', 'SCFI', 'KCCI', 'freight rate', 'surge', ...],
    '정상':       ['정상화', '안정', '회복', 'normalize', 'stable', ...],
}
```

---

## 9. 발표용 핵심 수치 (변경 금지)

| 항목 | 수치 | 출처 |
|---|---|---|
| LSTM MAPE | **9.4%** | 시간순 분할, 원단위 역정규화 |
| MRI 가중치 | G=0.132, D=0.132, F=0.183, V=0.437, P=0.115 | IQR 엔트로피+등분 하이브리드 |
| NLIC 창고 DB | **439개** | 국가물류통합정보센터 (부산 전 지역) |
| 홍해 유사사례 평균 | **지연 12.3일, 운임 +20.7%** | 7사건 DB, historical_matcher |
| 수에즈 통항 감소 | **42~90%** | UNCTAD 2024 |
| 호르무즈 LNG | **세계 20%** | EIA |
| MRI 역사 기간 | **136개월** (2015-02~2026-05) | GDELT v2 시작일 기준 |
| ODCY 보관료 | **10,000원/CBM/일** | 2024 부산항 업체 문의 |
| 외부 보세창고 | **4,000원/CBM/일** | 2024 부산항 업체 문의 |

---

## 10. API 엔드포인트 (api.py)

```
GET  /api/health                  서버 상태
GET  /api/mri                     현재 MRI + 등급 + 이슈 + 5차원 하위지수
GET  /api/mri/similar-events      과거 유사사례 (평균 지연·운임 포함)
GET  /api/mri/lstm-forecast       LSTM 3개월 예측 (캐시 우선)
GET  /api/routes                  항로 목록 5개
POST /api/shipment/register       화주 출하 등록 → 리스크 맥락 + 참고 추정 반환
POST /api/warehouse/recommend     NLIC DB → 거리 기준 5곳 + A/B/C 시나리오 비용
POST /api/routy/generate          Phase 1 루티 JSON 생성 (Phase 2 없음)
```

---

## 11. 절대 하지 말 것

- 화주에게 강제 시나리오 적용 — 참고 정보 제시만 허용
- 자기참조 회로: 학습 타깃 y를 입력 X 공식으로 만들지 않음
- LSTM 학습/검증에 random_split 사용 금지 — 시간순만
- BDI 사용 금지 (운임지수 → V 불적절, 2026-05 결정으로 완전 제거)
- Phase 2 루티 JSON 자동 생성 금지 — 화주 요청 시 별도 처리
- 트레드링스를 깎아내리지 말 것 — 보완재 포지셔닝 유지
