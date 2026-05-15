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
Step 2  MRI + 맥락   뉴스RSS → NLP → MRI 5차원 하이브리드 엔트로피 가중치 → 등급 판정
                      현재 이슈 한줄 요약 (뉴스 키워드 기반)
                      과거 유사사례(historical_matcher) 평균 지연·운임 참고 제시
                      LSTM 예측 (사전계산 캐시 또는 실시간)
Step 3  창고 추천     모든 고객 이용 가능 (MRI 등급 무관)
                      NLIC 정부DB(439개) + 카카오 API 병행 탐색
                      4가지 옵션(option_presenter) 비용 비교 제시
                      최종 결정은 화주 — 플랫폼은 추천만
Step 4  루티 JSON     Phase1(출발지→창고) JSON 생성 (Phase2 제거 — 선적재개는 화주 직접 결정)
```

---

## 핵심 설계 원칙

- **강제 시나리오 없음**: 플랫폼은 과거 유사사례 평균값을 참고로 제시할 뿐, 화주 행동을 강제하지 않음
- `build_risk_context()`: MRI + 유사사례 + 뉴스 키워드 → `RiskContext` 반환 (화주 제시용)
- `estimate_impact_advisory()`: 과거 평균 기반 참고 추정 (확정값 아님)
- Tab4 시뮬레이션: `auto_classify_scenario()` + `analyze_impact()` 는 시뮬 전용으로만 사용

---

## 파일 구조 및 역할

### src/ — 핵심 모듈

| 파일 | 역할 | 주요 함수 |
|---|---|---|
| `config.py` | 가중치·키워드·항로·등급 상수 | MRI_GRADES, RISK_KEYWORDS, ROUTE_INFO |
| `nlp_classifier.py` | 뉴스 키워드 분류 (한글+영어) | classify_news_df, top_category |
| `mri_engine.py` | 실시간 MRI 산출 (웹앱용) | calc_today_mri, build_mri_series, mri_grade |
| `lstm_forecaster.py` | 부산항 물동량 LSTM 예측 | train_and_forecast, build_main_df |
| `scenario_engine.py` | 리스크 맥락 구성 + (시뮬용) 시나리오 분류 | build_risk_context, estimate_impact_advisory, RiskContext |
| `reorganizer.py` | 권역 단위 운영 재조정 (Tab4 시뮬용) | reorganize_pickups |
| `routy_adapter.py` | 루티 JSON 생성 (Tab4 시뮬용) | generate_routy_input, run_all_scenarios |
| `historical_matcher.py` | 과거 유사사례 매칭 (7사건) | find_similar_events |
| `odcy_recommender.py` | NLIC DB + 카카오 API 창고 탐색 | recommend_storage, _load_nlic_db, CargoType |
| `option_presenter.py` | (레거시 유지) A/B/C/D 구버전 — 신규: scenario_cost.py 사용 |
| `storage_routy_adapter.py` | Phase 1/2 창고 운송 JSON | generate_storage_routy_json |
| `data_loader.py` | KCCI/BPA/ECOS 데이터 로더 | load_kcci, load_busan_throughput_combined |
| `real_data_fetcher.py` | RSS 뉴스·유가·환율 실시간 수집 | fetch_maritime_news (30일치, 소스당 30건) |
| `llm_reporter.py` | Gemini/Claude 자동 보고서 | generate_risk_report, active_llm_provider |
| `visualizer.py` | 시각화 | plot_lstm_loss, plot_mri_series |

### 루트 파일

| 파일 | 역할 |
|---|---|
| `api.py` | FastAPI 백엔드 (Lovable 연동용 REST API) |
| `app.py` | Streamlit 웹앱 (4탭 구조) |
| `notebooks/wemeet_v4_main.ipynb` | 발표용 메인 노트북 (29셀) |
| `render.yaml` | Render 클라우드 배포 설정 |
| `requirements-deploy.txt` | 배포용 의존성 (torch 제외) |

### 주요 데이터 파일

| 파일 | 내용 |
|---|---|
| `data/nlic_warehouses.json` | NLIC 부산 물류창고 439개 (좌표·면적·화물유형 포함) |
| `data/lstm_cache.json` | LSTM 사전계산 캐시 (Render 서버에서 torch 없이 작동) |
| `부산_물류창고정보_260509.xls` | NLIC 원본 Excel (geocode_nlic.py 재실행용) |

---

## MRI 5차원 설계 (하이브리드 엔트로피 가중치)

```
MRI = 0.132·G + 0.132·D + 0.183·F + 0.437·V + 0.115·P
(IQR 로버스트 엔트로피 + 등분 가중치(0.2) 단순 평균 — 다중공선성 보정)

G (지정학·항로): GDELT BigQuery + Naver DataLab (80:20)
D (운항방해):   GDELT 부정감성 비율 + Naver DataLab (80:20)
F (운임변동):   SCFI/CCFI(~2022-10) + KCCI(2022-11~) 월변화율
V (물동량):     BPA 부산항 12개월 롤링 YoY + LSTM 예측(공백 보완)
P (항만·통상):  GDELT 제재이벤트 + Naver DataLab (80:20)

MRI 등급: 정상(<0.33) / 주의(0.33~0.43) / 경계(0.43~0.55) / 위험(≥0.55)
          — 분위수 기반 (75th/91th/95th), 역사 136개월 실데이터
```

---

## RiskContext 구조 (화주 제시용)

```python
@dataclass
class RiskContext:
    mri: float
    grade: str                   # '정상' / '주의' / '경계' / '위험'
    grade_color: str
    top_category: str            # NLP 분류 최다 카테고리
    current_issue: str           # 뉴스 키워드 기반 한줄 요약
    top_keywords: list[str]
    similar_events: list[dict]   # historical_matcher 결과 (top 3)
    avg_delay_days: float        # 유사사례 평균 지연일 (MRI<0.3 → 0)
    avg_freight_change_pct: float
    warehouse_recommended: bool  # 항상 True (모든 고객 이용 가능)
    advisory_note: str           # 화주 제시 참고 문구
```

---

## 창고 탐색 우선순위

```
1순위: NLIC 국가물류통합정보센터 DB — data/nlic_warehouses.json (439개, 좌표 포함)
2순위: 카카오 Local API — 항만 반경 15km 실시간 검색
3순위: 내장 시뮬 DB — NLIC JSON 없을 때만 폴백 (9개 대표 창고)
```

NLIC 있으면 `simulation_mode = False` (정부 실데이터). 카카오 API 키 없어도 NLIC만으로 작동.

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
| cell[23] | **Step 3. ODCY 탐색** (NLIC+카카오) |
| cell[24] | A/B/C/D 옵션 비교 차트 |
| cell[25] | 지도 시각화 |
| cell[27] | **Step 4. 루티 JSON** (Phase1+2) |

---

## API 엔드포인트 (api.py)

```
GET  /api/health                  서버 상태
GET  /api/mri                     현재 MRI + 등급 + 이슈
GET  /api/mri/similar-events      과거 유사사례 (평균 지연·운임 포함)
GET  /api/mri/lstm-forecast       LSTM 3개월 예측 (캐시 우선)
GET  /api/routes                  항로 목록 5개
POST /api/shipment/register       화주 출하 등록 → 리스크 맥락 + 참고 추정 반환
POST /api/warehouse/recommend     창고·ODCY 추천 + 4옵션 비용
POST /api/routy/generate          Phase1+2 루티 JSON 생성
```

---

## 중요 데이터 소스

| 데이터 | 소스 | 비고 |
|---|---|---|
| KCCI 운임지수 | 한국해양진흥공사 XLS | 주간 업데이트 |
| 부산항 물동량 | BPA API (2020~2024) + Excel (2025) | BPA_API_KEY |
| 해사 뉴스 | RSS (gCaptain, Splash247, 한국해운신문) | feedparser, 30일치 |
| 창고 탐색 | NLIC DB(439개) → 카카오 Local API → 시뮬DB | KAKAO_REST_API_KEY |
| 경로 계산 | 카카오모빌리티 → Haversine 폴백 | KAKAO_MOBILITY_KEY |
| 유가 | Yahoo Finance BZ=F → FRED → EIA | 자동 수집 |
| 환율 | ECOS → frankfurter.app | ECOS_API_KEY |
| LLM 보고서 | Google Gemini → Claude Haiku | GEMINI_API_KEY |

---

## 코딩 규칙

- Python 3.10+, type hint 필수
- 시계열: random_split 절대 금지 → 시간순 분할만
- API 키: .env만, 코드에 하드코딩 금지
- 시드 고정: `np.random.seed(42)`, `torch.manual_seed(42)`
- LSTM MAPE: 정규화 공간 아닌 원단위(TEU) 역정규화 후 계산

## 절대 하지 말 것

- 화주에게 강제 시나리오 적용 — 참고 정보 제시만 허용
- 자기참조 회로: 학습 타깃 y를 입력 X 공식으로 만들지 않음
- 트레드링스를 깎아내리지 말 것 — 보완재 포지셔닝 유지

## 발표용 핵심 수치

- LSTM MAPE: **9.4%** (시간순 분할, 원단위)
- MRI 가중치: **하이브리드 엔트로피** (G=0.132, D=0.132, F=0.183, V=0.437, P=0.115)
- NLIC 창고 DB: **439개** (부산 전 지역, 지오코딩 완료)
- 홍해 유사사례 평균: **지연 12.3일, 운임 +20.7%**
- 수에즈 감소: **42~90%** (UNCTAD 2024)
- 호르무즈 LNG: **세계 20%** (EIA)
