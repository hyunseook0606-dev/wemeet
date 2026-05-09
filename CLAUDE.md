# CLAUDE.md

> 이 파일은 Claude Code가 세션 시작 시 자동으로 읽는 프로젝트 컨텍스트입니다.

---

## 프로젝트 개요

**프로젝트명**: 해상 리스크 대응형 공동 물류 운영·국내운송 연계 플랫폼
**연계 기업**: 위밋모빌리티 (Wemet Mobility)
**주관**: 한국해양수산개발원(KMI), 제5차 해운항만물류 인력양성사업
**대회**: 2026학년도 1학기 기업문제해결 프로젝트 및 공모전
**기간**: 2026.04.29 ~ 2026.05.20

---

## 플랫폼 흐름 (4단계 — 절대 변경 금지)

```
Step 1  화주 입력     화물종류·CBM·항로·납기·집화일 → SHIPPER_INPUT dict
Step 2  MRI 분석      뉴스RSS → NLP → MRI 5차원 AHP → 등급 판정
                      과거 유사사례(historical_matcher) + LSTM 예측
Step 3  창고 추천     MRI ≥ 0.5 시만 활성화
                      카카오 API → 창고·ODCY 탐색 → 4가지 옵션(option_presenter)
                      최종 결정은 화주 — 플랫폼은 추천만
Step 4  루티 JSON     Phase1(출발지→창고) + Phase2(창고→CY) JSON 생성
```

---

## 시나리오 시스템

| ID | 트리거 | 정책 | 파라미터 |
|---|---|---|---|
| A_NORMAL | MRI < 0.3 | AS_PLANNED | 변경 없음 |
| B_GEOPOLITICAL | MRI ≥ 0.7 + 지정학분쟁 | REROUTE_AND_HOLDBACK | +14일, +30% |
| C_WEATHER | MRI ≥ 0.5 + 기상재해 | HOLDBACK_NORMAL_RUSH_COLD | +5일, +5% |
| D_DELAY | MRI 0.3~0.5 | SHIFT_PICKUP | +3일, +2% |
| E_CANCELLATION | cancel_flag | REGROUP_REMAINING | 재구성 |

**B +14일**: 케이프타운 우회 실제 소요일 (변경 금지)
**B +30%**: 홍해 사태 실제 운임 증가율 (변경 금지)

---

## 파일 구조 및 역할

### src/ — 핵심 모듈

| 파일 | 역할 | 주요 함수 |
|---|---|---|
| `config.py` | 시나리오·AHP·키워드 상수 | SCENARIOS, MRI_AHP_WEIGHTS, RISK_KEYWORDS |
| `nlp_classifier.py` | 뉴스 키워드 분류 (한글+영어) | classify_news_df, top_category |
| `mri_engine.py` | MRI 5차원 AHP 산출 | calc_today_mri, build_mri_series |
| `lstm_forecaster.py` | 부산항 물동량 LSTM 예측 | train_and_forecast, build_main_df |
| `scenario_engine.py` | 시나리오 자동 분류 + 영향 분석 | auto_classify_scenario, analyze_impact |
| `reorganizer.py` | 권역 단위 운영 재조정 | reorganize_pickups |
| `routy_adapter.py` | 루티 JSON 생성 (5시나리오) | generate_routy_input, run_all_scenarios |
| `historical_matcher.py` | 과거 유사사례 매칭 (7사건) | find_similar_events |
| `odcy_recommender.py` | 카카오 API 창고·ODCY 탐색 | recommend_storage, CargoType |
| `option_presenter.py` | A/B/C/D 4가지 옵션 비용 산출 | generate_four_options |
| `storage_routy_adapter.py` | Phase 1/2 창고 운송 JSON | generate_storage_routy_json |
| `data_loader.py` | KCCI/BPA/ECOS 데이터 로더 | load_kcci, load_busan_throughput_combined |
| `real_data_fetcher.py` | RSS 뉴스·유가·환율 실시간 수집 | fetch_maritime_news, fetch_brent_oil_monthly |
| `llm_reporter.py` | Gemini/Claude 자동 보고서 | generate_risk_report, active_llm_provider |
| `visualizer.py` | 시각화 | plot_lstm_loss, plot_mri_series |

### 루트 파일

| 파일 | 역할 |
|---|---|
| `api.py` | FastAPI 백엔드 (Lovable 연동용 REST API) |
| `app.py` | Streamlit 웹앱 (4탭 구조) |
| `notebooks/wemeet_v4_main.ipynb` | 발표용 메인 노트북 (29셀) |

---

## MRI 5차원 설계

```
MRI = 0.431·G + 0.182·D + 0.253·F + 0.090·V + 0.044·P

G (지정학·항로): 뉴스비중/0.25 — 포화점 25%
D (지연·운항):  G×1.0 + 기상×0.36
F (운임 변동):  뉴스/0.20 × 50% + KCCI변동/0.15 × 50%
V (통행량):     KCCI감소/0.10 — 10% 감소=포화
P (항만·통상):  뉴스비중/0.20 — 포화점 20%

CR = 3.1% < 10% (AHP 일관성 통과)
```

**정규화 포화점 설계 이유**: RSS 전체 기사 중 단일 카테고리가 25% 이상 차지하기 어려움.
포화점 없이 비율 그대로 쓰면 시뮬(G=0.5~0.7)과 5배 괴리 발생.

---

## 노트북 셀 구조 (29셀)

| 셀 번호 | 내용 |
|---|---|
| cell[02] | 패키지 임포트, ROOT 경로 자동 설정 |
| cell[03] | 데이터 소스 현황 |
| cell[04] | KCCI 운임지수 XLS 로드 |
| cell[06] | **Step 1. 화주 입력** (SHIPPER_INPUT) |
| cell[07] | 뉴스 수집 (RSS 30일·소스당 30건) |
| cell[08] | NLP 분류 |
| cell[09] | AHP 계산 |
| cell[10] | AHP 시각화 |
| cell[11] | **Step 2. MRI 산출** (5차원) |
| cell[12] | MRI 시계열 시각화 |
| cell[14] | 거시경제 데이터 (BPA+Excel, 환율, 유가) |
| cell[15] | LSTM 학습 & 예측 |
| cell[17] | LSTM 고객 인사이트 차트 |
| cell[19] | 과거 유사사례 매칭 |
| cell[21] | 유사사례 시각화 |
| cell[23] | **Step 3. ODCY 탐색** (카카오 실데이터) |
| cell[24] | A/B/C/D 옵션 비교 차트 |
| cell[25] | 지도 시각화 |
| cell[27] | **Step 4. 루티 JSON** (Phase1+2) |

---

## API 엔드포인트 (api.py)

```
GET  /api/health                  서버 상태
GET  /api/mri                     현재 MRI + 시나리오
GET  /api/mri/similar-events      과거 유사사례
GET  /api/mri/lstm-forecast       LSTM 3개월 예측
GET  /api/routes                  항로 목록
POST /api/shipment/register       화주 출하 등록 + 영향 분석
POST /api/warehouse/recommend     창고·ODCY 추천 + 4옵션
POST /api/routy/generate          Phase1+2 루티 JSON 생성
```

---

## 중요 데이터 소스

| 데이터 | 소스 | API/파일 |
|---|---|---|
| KCCI 운임지수 | 한국해양진흥공사 | XLS 파일 또는 data.go.kr API |
| 부산항 물동량 | BPA API (2020~2024) + Excel (2025) | BPA_API_KEY |
| 해사 뉴스 | RSS (gCaptain, Splash247, 한국해운신문) | feedparser |
| 창고 탐색 | NLIC 공공DB(439개) → 카카오 Local API → 시뮬DB | KAKAO_REST_API_KEY |
| 경로 계산 | 카카오모빌리티 | KAKAO_MOBILITY_KEY (=REST 키) |
| 유가 | Yahoo Finance BZ=F (1순위) → FRED → EIA | 자동 수집 |
| 환율 | ECOS → frankfurter.app | ECOS_API_KEY |
| LLM 보고서 | Google Gemini (무료) → Claude Haiku (유료) | GEMINI_API_KEY |

---

## 코딩 규칙

- Python 3.10+, type hint 필수
- 시계열: random_split 절대 금지 → 시간순 분할만
- API 키: .env만, 코드에 하드코딩 금지
- 시드 고정: `np.random.seed(42)`, `torch.manual_seed(42)`
- LSTM MAPE: 정규화 공간 아닌 원단위(TEU) 역정규화 후 계산

## 절대 하지 말 것

- 자기참조 회로: 학습 타깃 y를 입력 X 공식으로 만들지 않음
- 트레드링스를 깎아내리지 말 것 — 보완재 포지셔닝 유지
- 시나리오 파라미터(+14일, +30%) 근거 없이 변경 금지

## 발표용 핵심 수치

- LSTM MAPE: **9.4%** (시간순 분할, 원단위)
- CO2 절감: **35%** (적재율 55%→85%)
- AHP CR: **3.1%** (< 10% 통과)
- 수에즈 감소: **42~90%** (UNCTAD 2024)
- 호르무즈 LNG: **세계 20%** (EIA)
