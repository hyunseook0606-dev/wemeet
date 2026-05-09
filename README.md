# 해상 리스크 대응형 공동 물류 운영 플랫폼

> 위밋모빌리티 × 한국해양수산개발원(KMI) — 2026년 1학기 기업문제해결 프로젝트

해상 공급망 리스크 발생 시 중소 수출기업의 출하 일정을 자동 재조정하고,
항만 주변 창고·ODCY를 AI로 탐색해 화주에게 4가지 대응 옵션을 제시하며,
그 결과를 위밋 루티/루티프로의 실행 입력 JSON으로 변환하는 운영 의사결정 플랫폼

---

## 플랫폼 흐름 (4단계)

```
Step 1  화주 입력        화물 종류·CBM·항로·납기·집화일 등록
   ↓
Step 2  MRI 분석         실시간 뉴스 → MRI 산출 → 등급 판정
                         과거 유사사례 평균 지연·운임 제공
                         LSTM 부산항 물동량 3개월 예측
   ↓
Step 3  창고 추천         MRI ≥ 0.5 시 활성화
(MRI ≥ 0.5)              카카오 API로 항만 주변 창고·ODCY 탐색
                         A/B/C/D 4가지 옵션 비용 비교 제시
                         최종 결정은 화주 — 플랫폼은 추천만
   ↓
Step 4  루티 연계 JSON    Phase 1 (출발지→창고) + Phase 2 (창고→CY)
                         루티/루티프로 API 입력용 표준 JSON 자동 생성
```

---

## 핵심 차별점

| 영역 | 기존 플랫폼 | 본 플랫폼 |
|---|---|---|
| 해상 가시성·ETA 예측 | ✅ 강점 (트레드링스, Flexport) | △ 보완재 |
| **선제적 리스크 의사결정** | ❌ | ✅ MRI 5차원 AHP + 시나리오 자동 분류 |
| **항만 창고 자동 탐색** | ❌ | ✅ 카카오 실데이터 + 4가지 옵션 비교 |
| **국내 내륙 배차 통합** | ❌ | ✅ 루티(ROOUTY) JSON 자동 생성 |
| **과거 유사사례 인사이트** | ❌ | ✅ historical_matcher (7개 실제 사건 DB) |

---

## 시나리오 시스템

| ID | 등급 | 트리거 | 대응 정책 |
|---|---|---|---|
| A_NORMAL | 🟢 정상 | MRI < 0.3 | 기존 계획 유지 |
| B_GEOPOLITICAL | 🔴 위험 | MRI ≥ 0.7 + 지정학분쟁 | 우회항로 + 운임 +30% |
| C_WEATHER | 🟠 경계 | MRI ≥ 0.5 + 기상재해 | 콜드체인 우선, +5일 |
| D_DELAY | 🟡 주의 | MRI 0.3~0.5 | 집화 일정 조정, +3일 |
| E_CANCELLATION | ⚪ | cancel_flag | 매칭 그룹 재구성 |

---

## 프로젝트 구조

```
vs code/
├── CLAUDE.md                      # Claude Code 컨텍스트
├── README.md                      # 이 파일
├── PROJECT_SPEC.md                # 상세 명세
├── SETUP_GUIDE.md                 # 설치·실행 가이드
├── TASKS.md                       # 작업 목록
├── requirements.txt               # Python 의존성
├── .env                           # API 키 (Git 제외)
├── .env.example                   # 환경변수 예시
│
├── api.py                         # ★ FastAPI 백엔드 (Lovable 연동)
├── app.py                         # Streamlit 웹앱
│
├── notebooks/
│   └── wemeet_v4_main.ipynb       # 발표용 메인 노트북 (29셀)
│
├── src/
│   ├── config.py                  # 시나리오 정의, AHP 가중치, 키워드
│   ├── data_loader.py             # KCCI / 부산항 BPA / ECOS 로더
│   ├── real_data_fetcher.py       # RSS 뉴스, 유가, 환율 실시간 수집
│   ├── freight_index_loader.py    # KCCI XLS 파일 파서
│   ├── nlp_classifier.py          # 키워드 사전 분류기 (한글+영어)
│   ├── mri_engine.py              # MRI 5차원 AHP 산출
│   ├── lstm_forecaster.py         # LSTM 부산항 물동량 예측
│   ├── scenario_engine.py         # ★ 시나리오 자동 분류 + 영향 분석
│   ├── reorganizer.py             # ★ 권역 단위 운영 재조정
│   ├── routy_adapter.py           # ★ 루티 JSON 어댑터 (5시나리오)
│   ├── historical_matcher.py      # ★ 과거 유사사례 매칭 (7개 이벤트)
│   ├── odcy_recommender.py        # ★ 카카오 API 창고·ODCY 탐색
│   ├── option_presenter.py        # ★ A/B/C/D 4가지 옵션 비용 산출
│   ├── storage_routy_adapter.py   # ★ Phase 1/2 창고 운송 JSON
│   ├── visualizer.py              # 시각화 (LSTM, MRI, 시나리오 KPI)
│   └── llm_reporter.py            # Gemini/Claude 자동 보고서 생성
│
├── data/                          # 실데이터 (선택)
│   ├── kcci_weekly.csv            # KCCI 운임지수 (XLS 합치기 결과)
│   ├── freight_index/             # KCCI XLS 원본 파일
│   ├── ecos_cache/                # 환율·유가 캐시 CSV
│   └── 260414_홈페이지 업데이트_전국항 및 부산항...xlsx  # 2025 물동량
│
├── routy_inputs/                  # 자동 생성 루티 JSON
│   └── EG-YYYYMMDD-{시나리오}.json
│
├── scripts/
│   ├── auto_update.py             # 일별 데이터 자동 갱신
│   └── _make_lovable_guide.py     # Lovable 가이드 DOCX 생성
│
└── tests/
    ├── test_scenario_engine.py
    ├── test_reorganizer.py
    ├── test_routy_adapter.py
    └── test_real_data_fetcher.py
```

---

## 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
# .env.example → .env 복사 후 키 입력
Copy-Item .env.example .env   # Windows PowerShell
```

최소 필요 키: `GEMINI_API_KEY` (무료), `KAKAO_REST_API_KEY` (무료)

### 3-A. 노트북 실행 (발표용)

```bash
jupyter notebook notebooks/wemeet_v4_main.ipynb
```

셀 순서대로 실행. 첫 번째 셀(Step 1)에서 화주 정보를 수정하세요.

### 3-B. Streamlit 웹앱 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속.

### 3-C. FastAPI 백엔드 실행 (Lovable 연동)

```bash
uvicorn api:app --reload --port 8000
```

`http://localhost:8000/docs` 에서 모든 API 테스트 가능.

### 4. 단위 테스트

```bash
pytest tests/ -v
```

---

## 핵심 KPI

| 지표 | 값 | 근거 |
|---|---|---|
| LSTM 검증 MAPE | **9.4%** | 시간순 80/20 분할, 원단위 역정규화 |
| CO2 절감률 | **35%** | 적재율 55% → 85% 향상 (CBAM 대응) |
| 지정학 시나리오 지연 | **+14일** | 케이프타운 우회 실제 소요일 |
| 지정학 시나리오 운임 | **+30%** | 홍해 사태 실제 증가율 (UNCTAD 2024) |
| 수에즈 통항 감소 | **42~90%** | UNCTAD 2024 실측 데이터 |
| AHP 일관성 비율 | **CR=3.1%** | < 10% 기준 통과 |

---

## API 키 현황

| API | 용도 | 비용 | 없으면 |
|---|---|---|---|
| Google Gemini | LLM 자동 보고서 | 무료 (1,500회/일) | 보고서 기능 비활성화 |
| 카카오 Local | 창고·ODCY 탐색 | 무료 (300,000건/일) | 시뮬레이션 DB 사용 |
| 카카오모빌리티 | 경로·거리 계산 | 무료 (5,000건/일) | Haversine 추정 대체 |
| ECOS | 환율·유가·GDP | 무료 | Yahoo Finance 자동 대체 |
| BPA | 부산항 물동량 | 무료 | Excel + 계절분해 대체 |

---

## Lovable 프론트엔드 연동

`Lovable_연동_개발가이드.docx` 참조.
FastAPI 백엔드(`api.py`)를 먼저 실행한 후 Lovable에서 프롬프트로 화면을 생성합니다.

---

## 주관 기관

- **주관**: 한국해양수산개발원(KMI), 제5차 해운항만물류 인력양성사업
- **연계 기업**: 위밋모빌리티 (Wemet Mobility)
- **루티 연동**: 현재 시뮬레이션 모드 (`integration_status = 'simulation_mode'`)
  → API 발급 시 `'live_api'`로 전환만 하면 즉시 연동 가능한 구조
