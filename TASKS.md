# TASKS.md — Claude Code 작업 지시 목록

> 이 파일을 Claude Code에게 보여주고 작업을 진행해 주세요.
> 각 작업은 독립적으로 실행 가능하며, 순서대로 진행하는 것을 권장합니다.
> Claude Code 사용법: 작업을 시작하기 전에 `@CLAUDE.md @PROJECT_SPEC.md`를 먼저 읽도록 지시.

---

## 작업 진행 방법 (Claude Code 사용 가이드)

### 첫 세션 시작 시
```
@CLAUDE.md @PROJECT_SPEC.md @TASKS.md
이 프로젝트의 컨텍스트를 모두 읽고, 작업 1-1부터 시작해줘.
각 작업 완료 후 요약 보고하고, 다음 작업 진행 여부 확인 후 진행.
```

### 권장 워크플로우
1. **계획 모드(Plan Mode)** 활용: 큰 작업 전에 Claude가 먼저 계획을 보여주고 승인받음
2. **Extended Thinking** 토글 켜기: 시나리오 엔진 같은 복잡한 로직 작성 시
3. **Auto-accept 끄기**: 처음에는 모든 변경사항 직접 검토 (신뢰가 쌓이면 켜도 됨)

### 자주 쓰는 명령어
- `/init` — CLAUDE.md 자동 생성 (이미 있으면 스킵)
- `/compact` — 컨텍스트 길어지면 요약 압축
- `/code-review` — 작성된 코드 자체 리뷰
- `@파일명` — 특정 파일 컨텍스트로 첨부
- `Cmd/Ctrl+N` — 새 대화 시작

---

## 1주차: 프로젝트 셋업 + Part 1 이식

### 작업 1-1. 프로젝트 초기 설정

**목표**: 디렉토리 구조 + 기본 설정 파일 생성

**Claude Code 지시 예시**:
```
@CLAUDE.md @PROJECT_SPEC.md
다음을 생성해 줘:
1. requirements.txt (pandas, numpy, scikit-learn, xgboost, torch, plotly,
   matplotlib, seaborn, requests, beautifulsoup4, jupyter, pytest 포함)
2. .gitignore (Python 표준 + data/, routy_inputs/, .env)
3. .claudeignore (data/, *.csv, .ipynb_checkpoints/, __pycache__/)
4. src/, tests/, notebooks/, data/, routy_inputs/ 빈 폴더 + __init__.py
5. .env.example (ECOS_API_KEY=your_key_here)
```

**검증**: `tree -L 2`로 폴더 구조 확인

---

### 작업 1-2. Config 모듈 작성

**목표**: 시나리오 정의 + 상수를 한 곳에 집중

**파일**: `src/config.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 의 섹션 1, 4, 6을 참조해서 src/config.py를 작성해 줘.
- SCENARIOS 딕셔너리 (5개 시나리오, PROJECT_SPEC.md와 정확히 일치)
- ROUTE_INFO 딕셔너리 (5개 항로)
- LCL_MULTIPLIER, REGIONS, CARGO_TYPES, COMPANIES 상수
- MRI_WEIGHTS, MRI_GRADES 상수
- RISK_KEYWORDS, RISK_WEIGHTS, NEG_WORDS, POS_WORDS

타입 힌트 필수, 모든 상수는 대문자, 한글 주석 OK.
```

**검증**:
```python
from src.config import SCENARIOS, ROUTE_INFO
assert len(SCENARIOS) == 5
assert SCENARIOS['B_GEOPOLITICAL']['delay_days'] == 14
assert SCENARIOS['B_GEOPOLITICAL']['freight_surge_pct'] == 0.30
assert ROUTE_INFO['부산→LA']['usd_per_teu'] == 2300
```

---

### 작업 1-3. 데이터 로더 작성

**목표**: KCCI / 부산항 / ECOS API 통합 로더

**파일**: `src/data_loader.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 의 섹션 9를 참조해서 src/data_loader.py 작성:

함수 3개:
1. load_kcci(data_dir: Path, use_real: bool = True) -> pd.DataFrame | None
   - data/kcci.csv 자동 감지 (인코딩: utf-8/cp949/euc-kr)
   - 컬럼명 자동 감지 (발표일/일자, KCCI/종합지수)
   - 실패 시 None 반환 (시뮬 폴백)

2. load_throughput(data_dir: Path, use_real: bool = True) -> pd.DataFrame | None
   - data/busan_throughput.csv 로드
   - 단위 자동 변환 (TEU/천 TEU → 만 TEU)
   - 평균값 200만 근처여야 정상

3. fetch_ecos(stat_code, item_code, start_ym, end_ym, api_key, cache_dir) -> pd.DataFrame | None
   - ECOS API 호출
   - data/ecos_cache/ 에 캐시 저장
   - 환경변수 ECOS_API_KEY 사용 (os.getenv)

각 함수에 docstring 필수, type hint 필수.
실패 시 친절한 에러 메시지 print + None 반환.
```

**검증**: 시뮬 모드(use_real=False)에서도 None을 깔끔히 반환

---

### 작업 1-4. NLP 분류기 + MRI 엔진

**목표**: v3 코드의 셀 6, 9 로직을 모듈로 분리

**파일**: `src/nlp_classifier.py`, `src/mri_engine.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 섹션 6, 7 참조.

src/nlp_classifier.py:
- classify_risk(text: str) -> dict 함수
- 반환: {'category', 'risk_weight', 'keyword_hits', 'sentiment'}
- config의 RISK_KEYWORDS, RISK_WEIGHTS, NEG/POS_WORDS 사용

src/mri_engine.py:
- compute_mri_series(news_df, freight_df, dates) -> pd.DataFrame 함수
- compute_today_mri(news_df, freight_df) -> tuple[float, str, str] 함수
- 가중치 0.40 / 0.30 / 0.20 / 0.10 (PROJECT_SPEC와 일치)
- 등급 분류 (mri_grade 함수)

홍해 사태 (2023-12 ~ 2024-06) + 미중 관세 (2025-04~) 패턴 반영.
freight_df가 None이면 시뮬 폴백.
```

**검증**:
```python
from src.nlp_classifier import classify_risk
result = classify_risk("호르무즈 봉쇄, 운임 급등")
assert result['category'] == '지정학분쟁'  # '봉쇄'+'호르무즈' 매칭
assert result['risk_weight'] == 1.0
```

---

### 작업 1-5. LSTM 예측기

**목표**: 시간순 분할 + LSTM 학습/예측

**파일**: `src/lstm_forecaster.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 섹션 8 참조.

src/lstm_forecaster.py:

1. TimeSeriesDataset 클래스 (PyTorch Dataset)
2. LSTMModel 클래스 (2층 LSTM + Dropout 0.2 + FC)
3. train_lstm(main_df, features, lookback=12, horizon=3, epochs=50) 함수
   - ★ 시간순 분할 필수 (random_split 절대 금지)
   - 시드 고정 (np.random.seed(42), torch.manual_seed(42))
   - Adam optimizer, ReduceLROnPlateau scheduler
   - gradient clipping (max_norm=1.0)
4. predict_future(model, scaler, last_seq) -> np.ndarray
5. evaluate_mape(model, val_loader) -> float

PyTorch 미설치 환경 대응 (try/except + 명확한 에러 메시지).
```

**검증**:
```python
# 시간순 분할 확인
from src.lstm_forecaster import train_lstm
# 학습 시 train_indices = [0, 1, ..., 0.8N-1], val_indices = [0.8N, ..., N-1]
# 절대 random_split이 코드에 등장하면 안 됨
```

---

### 작업 1-6. 단위 테스트 작성 (1주차 검증)

**파일**: `tests/test_config.py`, `tests/test_nlp_classifier.py`, `tests/test_mri_engine.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 섹션 11 검증 체크리스트 참조.

각 모듈에 대한 pytest 단위 테스트 작성:

tests/test_config.py:
- 시나리오 5개 존재
- B_GEOPOLITICAL의 delay_days=14, freight_surge_pct=0.30
- ROUTE_INFO 5개 항로 모두 존재

tests/test_nlp_classifier.py:
- '호르무즈 봉쇄' → '지정학분쟁'
- '태풍 북상' → '기상재해'
- '관세 부과' → '관세정책'
- '정상화 회복' → '정상' + sentiment='positive'

tests/test_mri_engine.py:
- compute_today_mri 반환값이 0~1 범위
- 부정 뉴스 100% + 이벤트 100%면 MRI 최소 0.7 이상
- mri_grade(0.85) == '🔴 위험'

pytest tests/ -v 로 실행 가능해야 함.
```

**검증**: `pytest tests/ -v` 실행 시 전체 PASS

---

## 2주차: Part 2 시나리오 시스템 + 통합

### 작업 2-1. 시나리오 엔진 ⭐ 핵심

**목표**: 자동 분류 + 영향 분석

**파일**: `src/scenario_engine.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 섹션 1, 2 참조.

src/scenario_engine.py:

1. ShipmentRequest dataclass (PROJECT_SPEC 2.1과 정확히 일치)

2. ImpactAnalysis dataclass (PROJECT_SPEC 2.2와 정확히 일치)

3. auto_classify_scenario(today_mri, top_category, cancel_count) -> str
   - PROJECT_SPEC 1.2의 우선순위 규칙 정확히 구현
   - 반환: 'A_NORMAL' / 'B_GEOPOLITICAL' / ...

4. analyze_impact(shipment, scenario, cancelled_ids=None) -> ImpactAnalysis
   - 각 시나리오 정책별 분기 처리
   - 항로 필터 (B 시나리오는 affects_routes만)
   - 콜드체인 우선처리 + 보류 + 우회 판단

5. generate_shipments(n=30, seed=42) -> pd.DataFrame
   - 시뮬용 출하 예정 건 생성 (PROJECT_SPEC 2.1 형식)
   - 화물 유형 분포: 일반 65%, 냉장 25%, 위험물 10%
   - 긴급 화물 15%

함수마다 docstring + type hint 필수.
analyze_impact는 순수 함수 (사이드 이펙트 없음).
```

**검증**:
```python
from src.scenario_engine import auto_classify_scenario, analyze_impact
from src.config import SCENARIOS

assert auto_classify_scenario(0.85, '지정학분쟁') == 'B_GEOPOLITICAL'
assert auto_classify_scenario(0.65, '기상재해') == 'C_WEATHER'
assert auto_classify_scenario(0.10, '정상') == 'A_NORMAL'
assert auto_classify_scenario(0.20, '정상', cancel_count=3) == 'E_CANCELLATION'
```

---

### 작업 2-2. 운영 재조정 엔진 ⭐ 핵심

**파일**: `src/reorganizer.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 섹션 3 참조.

src/reorganizer.py:

1. reorganize_pickups(ship_df, impacts, scenario) -> dict
   반환 구조:
   {
       'pickup_holdback': [...],         # 항만 반입 보류
       'pickup_shifted':  [...],         # 집화 일정 조정
       'pickup_priority': [...],         # 우선처리 (콜드체인/긴급)
       'consolidation_groups': [...],    # 권역 통합 그룹
   }

2. 행동 분류 우선순위 (PROJECT_SPEC 3.1):
   PRIORITY > HOLDBACK > SHIFT

3. 권역 통합 매칭 규칙 (PROJECT_SPEC 3.2):
   - 같은 region
   - 같은 cargo_type (호환성 매트릭스 적용)
   - 새 집화일 ±2일
   - 그룹당 최소 2건
   - 절감 추정 15%

CARGO_COMPAT 딕셔너리는 config.py에서 import.
순수 함수, 데이터 변경 없음.
```

**검증**:
```python
# B 시나리오에서 부산→로테르담 화주만 영향받는지
# C 시나리오에서 콜드체인이 PRIORITY로 분류되는지
```

---

### 작업 2-3. 루티 어댑터

**파일**: `src/routy_adapter.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 섹션 5 참조.

src/routy_adapter.py:

1. generate_routy_input(scenario_id, scenario, ship_df, impacts, reorg) -> dict
   - PROJECT_SPEC 5.1 JSON 스키마와 정확히 일치
   - meta.integration_status = 'simulation_mode'

2. save_routy_input(routy_input, output_dir='routy_inputs') -> Path
   - 파일명: EG-{YYYYMMDD}-{SCENARIO_ID}.json
   - UTF-8 인코딩, indent=2, ensure_ascii=False

3. load_routy_input(file_path) -> dict
   - 검증용 (저장한 JSON 다시 읽기)

JSON 직렬화 시 datetime 객체는 isoformat() 사용.
모든 숫자는 int/float (numpy 타입 직렬화 주의).
```

**검증**:
```python
import json
from src.routy_adapter import generate_routy_input, save_routy_input

routy_input = generate_routy_input(...)
fp = save_routy_input(routy_input)
with open(fp) as f:
    loaded = json.load(f)
assert loaded['meta']['integration_status'] == 'simulation_mode'
```

---

### 작업 2-4. 시각화 모듈

**파일**: `src/visualizer.py`

**Claude Code 지시**:
```
src/visualizer.py에 시각화 함수 5개:

1. plot_mri_timeseries(mri_df) — MRI 시계열 + 등급 임계선
2. plot_scenario_comparison(results) — 5개 시나리오 비교 (4개 subplot)
   - 영향 받는 출하 건수
   - 행동 분류 stacked bar
   - 비용 영향 (색상: 양수 빨강, 음수 초록)
   - 납기 위반 건수
3. plot_pickup_adjustments(ship_df, reorg) — 권역별 집화 일정 변화
4. plot_consolidation_map(reorg, ship_df) — 권역 통합 그룹 시각화
5. dashboard_streamlit(results) — Plotly 인터랙티브 대시보드 (선택)

한글 폰트 자동 설정 (Malgun Gothic / AppleGothic / NanumGothic).
색상은 SCENARIOS의 'color' 필드 사용 (일관성).
```

**검증**: 시각화가 발표용으로 가독성 좋은지 직접 확인

---

### 작업 2-5. 메인 노트북 작성

**파일**: `notebooks/wemeet_v4_main.ipynb`

**Claude Code 지시**:
```
@CLAUDE.md @PROJECT_SPEC.md
notebooks/wemeet_v4_main.ipynb 생성. 구조:

# Part 1 — 평상시 운영
1. 환경 설정 (src 모듈 import)
2. 뉴스 수집 (시뮬 데이터, src.nlp_classifier 사용)
3. NLP 분류 결과
4. 데이터 로더 (data_loader.load_kcci 등)
5. MRI 산출 + 시각화
6. 부산항 물동량 + 거시경제
7. LSTM 학습 + MAPE

# Part 2 — 시나리오 기반 운영 재조정
8. 시나리오 정의 + 자동 분류 (현재 MRI/카테고리로 분류)
9. 출하 예정 건 등록 (30건)
10. 영향 분석 (자동 분류된 시나리오)
11. 운영 재조정
12. 루티 JSON 출력 + 파일 저장

# Part 3 — 통합 시연
13. 5개 시나리오 일괄 실행 비교 표
14. KPI 대시보드 (visualizer.plot_scenario_comparison)
15. 케이스 스터디 (경기남부 A/B/C 콜드체인 호르무즈 봉쇄)

각 셀 코드는 짧게 (최대 30줄).
주석으로 어떤 모듈 함수를 호출하는지 표시.
모든 셀이 위에서 아래로 순차 실행 가능해야 함.
```

**검증**: `jupyter nbconvert --execute notebooks/wemeet_v4_main.ipynb` 에러 0건

---

### 작업 2-6. 통합 테스트

**파일**: `tests/test_scenario_engine.py`, `tests/test_reorganizer.py`, `tests/test_routy_adapter.py`

**Claude Code 지시**:
```
@PROJECT_SPEC.md 섹션 11 체크리스트 참조.

3개 테스트 파일 작성:

test_scenario_engine.py:
- 자동 분류 (5가지 케이스)
- 영향 분석 (각 시나리오별 1건씩)
- A 시나리오: 영향 0건
- B 시나리오: 부산→로테르담만 영향

test_reorganizer.py:
- C 시나리오 + 냉장화물 → PRIORITY
- D 시나리오 + 일반화물 + 3일 지연 → HOLDBACK
- 권역 통합 그룹: 같은 권역 + 호환 화물 + ±2일 → 그룹 형성

test_routy_adapter.py:
- JSON 스키마 검증 (필수 키 존재)
- meta.integration_status == 'simulation_mode'
- 파일 저장 후 재로드 성공
- 파일명 형식 EG-YYYYMMDD-{ID}.json

pytest --cov=src tests/ 로 80% 이상 커버리지 목표.
```

**검증**: `pytest tests/ -v --cov=src` PASS + 커버리지 80%+

---

## 3주차: 발표 준비

### 작업 3-1. 발표용 시각화 보강

**Claude Code 지시**:
```
notebooks/wemeet_v4_main.ipynb 의 시각화 셀들을
발표용으로 다음과 같이 강화:

1. 모든 차트에 제목/범례/단위 명시
2. 색상은 SCENARIOS['color'] 일관성 유지
3. 케이스 스터디 시각화 추가 (gantt-style 일정 비교)
4. 5개 시나리오 비교 표를 Plotly Table로 인터랙티브 변환
5. 루티 JSON 미리보기는 syntax highlighting (rich.print 또는 IPython.display)

발표 시 화면에서 잘 보이도록 figsize 키우고 fontsize 16+.
```

---

### 작업 3-2. 발표 자료 (별도 .pptx 또는 .md)

**파일**: `presentation/slides.md` (Marp 또는 Reveal.js로 변환 가능)

**Claude Code 지시**:
```
@CLAUDE.md @README.md @PROJECT_SPEC.md
presentation/slides.md를 작성해 줘. 18장 구성:

1. 표지
2. 문제 정의 (해상 공급망 리스크 → 국내 운송 전이 구조)
3. 기존 플랫폼 한계 (트레드링스/Flexport는 항만까지)
4. 본 플랫폼 핵심 컨셉 (한 줄 정의)
5. 시스템 아키텍처 (3층 구조 다이어그램)
6. Part 1: MRI 엔진 (가중치 + 시계열 그래프)
7. Part 1: LSTM 물동량 예측 (시간순 분할 강조)
8. Part 2: 시나리오 시스템 (5종 비교 표)
9. Part 2: 시나리오 자동 분류기 (의사결정 플로우)
10. Part 2: 영향 분석 + 운영 재조정 (4가지 행동)
11. Part 2: 루티 JSON 출력 (실제 JSON 샘플)
12. 케이스 스터디: 호르무즈 봉쇄 (경기남부 A/B/C)
13. 5개 시나리오 비교 결과 (KPI 대시보드 캡처)
14. 위밋이 해야 하는 이유 (1억 건 실주행 데이터 + 트렌드 리포트)
15. 트레드링스/Flexport와의 차별점 (보완재 포지셔닝)
16. 향후 확장 (KoBERT, Hungarian, AIS 실시간, CBAM)
17. Q&A 카드 (예상 질문 6개)
18. 감사합니다

각 슬라이드 본문은 200자 이내, 시각 자료 우선.
```

---

### 작업 3-3. 모의 발표용 시연 스크립트

**파일**: `presentation/demo_script.md`

**Claude Code 지시**:
```
presentation/demo_script.md 작성:

발표 시간: 본발표 12분 + Q&A 8분

라이브 시연 흐름 (3분):
0:00-0:30  Part 1 환경 점검 (MRI 산출 결과 보여주기)
0:30-1:30  Part 2 자동 분류 시나리오 보여주기
1:30-2:30  5개 시나리오 일괄 실행 (KPI 대시보드)
2:30-3:00  호르무즈 케이스 스터디 + JSON 출력 보여주기

백업 영상 녹화 가이드:
- OBS Studio 설정
- 인터넷 끊김 대비
- 시연 흐름 1회 녹화 후 1.5배속 백업

Q&A 카드 (Markdown 표 형식):
Q1. BERT 미사용 사유
Q2. 정확도 50% 의미
Q3. 트레드링스와의 차이
Q4. Hungarian 미적용 사유
Q5. 루티 API 연동 방법
Q6. 화주 데이터 어디서?
(이미 신청서 v2와 정합되는 답변 보유)
```

---

### 작업 3-4. 최종 검증 + 디버그

**Claude Code 지시**:
```
다음을 모두 점검:

1. /code-review 명령어로 src/ 전체 자체 리뷰
2. pytest tests/ -v --cov=src (모든 테스트 PASS, 커버리지 80%+)
3. jupyter nbconvert --execute notebooks/wemeet_v4_main.ipynb (에러 0)
4. PROJECT_SPEC.md 섹션 11 체크리스트 모두 PASS:
   - 부산항 평균 200만 TEU 근처
   - 운임 방향성 30~70% 범위
   - LSTM 시간순 분할
   - A/B/C/D/E 시나리오 모두 정상 동작
   - JSON 파일 저장 확인

5. 발표 직전 백업:
   git add . && git commit -m "Final v4 demo ready"
   백업 USB에 전체 폴더 복사
```

---

## 핵심 주의사항 (Claude Code에게 강조)

### 절대 변경하지 말 것 (CLAUDE.md, PROJECT_SPEC.md에서 정의됨)
- 시나리오 5개의 모든 파라미터
- MRI 가중치 (0.40 / 0.30 / 0.20 / 0.10)
- 운임 계산 공식 (LCL_MULTIPLIER = 1.5)
- 항로 5개의 거리·운임·소요일
- 발표용 정량 수치 (50%, 35%, +30%, 200만 TEU)

### 시간순 분할 절대 사수 (data leakage 방지)
- LSTM 학습 시 `random_split` 절대 금지
- 검증 데이터는 학습 데이터의 미래 시점만

### 자기참조 회로 절대 금지
- 학습 타깃 y를 입력 X 공식으로 만들지 않음
- y는 외부 실측치(KCCI 다음 달 변동) 또는 외부 잠재 변수(AR-1)에서 나옴

### 신청서 톤다운 표현 유지
- "본 단계 / 향후 확장" 구분 명시
- 트레드링스 깎아내리지 말 것 (보완재 포지셔닝)

---

## 프로젝트 완료 시 산출물

```
✅ src/ 모듈 8개 (config, data_loader, nlp_classifier, mri_engine,
                  lstm_forecaster, scenario_engine, reorganizer,
                  routy_adapter, visualizer)
✅ tests/ 7개 테스트 파일 (커버리지 80%+)
✅ notebooks/wemeet_v4_main.ipynb (3 Part 통합)
✅ data/ KCCI/부산항/ECOS 캐시
✅ routy_inputs/ 5개 시나리오별 JSON
✅ presentation/slides.md
✅ presentation/demo_script.md
✅ 모의 발표 영상 백업
```

준비 완료 후 발표 진행.
