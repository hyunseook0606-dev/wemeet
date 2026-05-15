# 해상 리스크 대응형 공동 물류 운영 플랫폼

> 위밋모빌리티 × 한국해양수산개발원(KMI) — 2026년 1학기 기업문제해결 프로젝트

해상 공급망 리스크 발생 시 중소 수출기업에게 **과거 유사사례 기반 참고 정보**를 제시하고,
항만 주변 창고·ODCY를 자동 탐색해 **A/B/C 3가지 보관 시나리오 비용**을 비교하며,
화주가 선택한 결과를 위밋 루티(ROOUTY) 입력 JSON으로 변환하는 의사결정 지원 플랫폼

---

## 라이브 데모

- **웹 플랫폼**: `frontend/` (React + Vite, 로컬 포트 3000)
- **백엔드 API**: https://wemeet-api-dchk.onrender.com
- **API 문서(Swagger)**: https://wemeet-api-dchk.onrender.com/docs

---

## 플랫폼 흐름 (4단계)

```
Step 1  화주 입력        화물 종류·CBM·항로·납기·집화일 등록
   ↓
Step 2  MRI 분석         실시간 뉴스 RSS → NLP → 5차원 MRI 산출
                         하이브리드 엔트로피 가중치 → 등급 판정
                         현재 이슈 자동 요약 (뉴스 키워드 기반)
                         과거 유사사례 평균 지연·운임 참고 제공
                         LSTM 부산항 물동량 3개월 예측
   ↓
Step 3  창고 추천         모든 고객 이용 가능 (MRI 등급 무관)
                         NLIC 정부DB(439개) 거리 기준 5곳 추천
                         A/B/C 3가지 시나리오 비용 비교 (원화 기준)
                         최종 결정은 화주 — 플랫폼은 추천만
   ↓
Step 4  루티 JSON         Phase 1 (출발지→보세창고) JSON 자동 생성
                         Phase 2는 화주가 선적 재개 시점 결정 후 별도 운송 지시
```

---

## 핵심 차별점

| 영역 | 기존 플랫폼 | 본 플랫폼 |
|---|---|---|
| 해상 가시성·ETA 예측 | ✅ 강점 (트레드링스, Flexport) | △ 보완재 포지셔닝 |
| **선제적 리스크 맥락 제시** | ❌ | ✅ MRI 5차원 하이브리드 엔트로피 + 과거 유사사례 평균 참고 |
| **항만 창고 자동 탐색** | ❌ | ✅ NLIC 정부DB 439개 + 카카오 실데이터 |
| **국내 내륙 배차 통합** | ❌ | ✅ 루티(ROOUTY) JSON 자동 생성 |
| **과거 유사사례 인사이트** | ❌ | ✅ historical_matcher (7개 실제 사건 DB) |

---

## MRI 5차원 설계 (하이브리드 엔트로피 가중치)

```
MRI = 0.132·G + 0.132·D + 0.183·F + 0.437·V + 0.115·P

G (지정학·항로): GDELT + Naver DataLab (80:20)   → 0.132
D (운항방해):   GDELT 부정감성 + 뉴스 빈도       → 0.132
F (운임변동):   KCCI/SCFI 월변화율               → 0.183
V (물동량):     BPA 부산항 YoY + LSTM 예측        → 0.437
P (항만·통상):  GDELT 제재이벤트 + Naver DataLab  → 0.115

가중치 방법: IQR 로버스트 엔트로피 + 등분 하이브리드 (다중공선성 보정)
데이터 범위: 2015-02 ~ 현재 (GDELT v2 시작일 기준, 136개월)
```

---

## MRI 등급 기준 (분위수 기반)

| 등급 | 범위 | 통계 근거 | 창고 추천 |
|---|---|---|---|
| 🟢 정상 | < 0.33 | 75th 퍼센타일 미만 | ✅ 모든 고객 |
| 🟡 주의 | 0.33 ~ 0.43 | 75~91th | ✅ 모든 고객 |
| 🟠 경계 | 0.43 ~ 0.55 | 91~95th | ✅ 모든 고객 |
| 🔴 위험 | ≥ 0.55 | 상위 5% | ✅ 모든 고객 |

> 창고 추천은 MRI 등급과 무관하게 **모든 고객이 이용 가능**합니다.

**과거 유사사례 기반 참고값** (확정값 아님):
- 홍해 사태(2023~2024): 지연 12.3일, 운임 +20.7%
- 수에즈 에버기븐(2021): MRI 0.65 기록

---

## 시나리오 A/B/C 비용 기준

| 시나리오 | 내용 | 단가 | 권장 |
|---|---|---|---|
| A — 무대응 → ODCY | CY 5일 무료 후 ODCY 이송 | 10,000원/CBM/일 + 이송비 15만원 | — |
| B — 무대응 → CY 장치 | ODCY 만석, CY 초과 장치료 | 30,000원/CBM/일 (최고가) | — |
| C — 보세창고 선이송 | MRI 감지 → 출발지에서 직접 이송 | 4,000원/CBM/일 + 이송비 10만원 | ★ |

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/health` | 서버 상태 확인 |
| GET | `/api/mri` | 실시간 MRI + 등급 + 하위지수 (`?refresh=true` 캐시 무효화) |
| GET | `/api/mri/similar-events` | 과거 유사사례 매칭 (평균 지연·운임) |
| GET | `/api/mri/lstm-forecast` | LSTM 부산항 물동량 3개월 예측 |
| GET | `/api/routes` | 항로 목록 (5개) |
| POST | `/api/shipment/register` | 화주 출하 등록 → MRI + 리스크 맥락 반환 |
| POST | `/api/warehouse/recommend` | 창고 5곳 추천 + A/B/C 시나리오 비용 |
| GET | `/api/warehouse/calc_cost` | 화주 직접 입력 가격으로 총 비용 계산 |
| POST | `/api/routy/generate` | Phase 1 루티 JSON 생성 |

---

## 프로젝트 구조

```
wemeet/
├── README.md
├── CLAUDE.md                          # Claude Code 프로젝트 컨텍스트
├── PROJECT_SPEC.md                    # 상세 기술 명세
├── 발표_심사_질의응답_대응가이드.md     # 평가위원 예상 Q&A 20문항
│
├── api.py                             # FastAPI 백엔드 (9개 엔드포인트)
├── app.py                             # Streamlit 웹앱 (발표용 4탭)
│
├── requirements.txt                   # Python 의존성 (로컬, torch 포함)
├── requirements-deploy.txt            # Python 의존성 (Render 배포, torch 제외)
├── render.yaml                        # Render 클라우드 배포 설정
│
├── frontend/                          # React + Vite 웹 플랫폼
│   ├── src/
│   │   ├── components/
│   │   │   ├── Platform.jsx           # 4단계 플랫폼 데모 (메인)
│   │   │   ├── LiveMRI.jsx            # 실시간 MRI 대시보드
│   │   │   ├── Features.jsx           # 기능 소개
│   │   │   ├── HowItWorks.jsx         # 4단계 흐름 설명
│   │   │   ├── KakaoMap.jsx           # 카카오맵 창고 시각화
│   │   │   ├── Hero.jsx               # 히어로 섹션
│   │   │   ├── Stats.jsx              # 주요 수치
│   │   │   ├── Navbar.jsx
│   │   │   └── Footer.jsx
│   │   └── hooks/
│   │       └── useApi.js              # Render API 연동 (axios)
│   └── package.json
│
├── notebooks/
│   └── wemeet_v4_main.ipynb           # 발표용 메인 노트북
│
├── src/
│   ├── config.py                      # 하이브리드 엔트로피 가중치, 키워드, 항로
│   ├── data_loader.py                 # KCCI / BPA / ECOS 로더
│   ├── real_data_fetcher.py           # RSS 뉴스, 유가, 환율 실시간 수집
│   ├── freight_index_loader.py        # KCCI XLS 파일 파서
│   ├── nlp_classifier.py              # 키워드 사전 분류기 (한글+영어)
│   ├── mri_engine.py                  # MRI 5차원 하이브리드 엔트로피 산출
│   ├── lstm_forecaster.py             # LSTM 부산항 물동량 예측
│   ├── scenario_engine.py             # 리스크 맥락 구성 (build_risk_context)
│   ├── scenario_cost.py               # A/B/C 시나리오 비용 산출 (원화)
│   ├── reorganizer.py                 # 공동물류 그룹 편성 (참고용 보존)
│   ├── routy_adapter.py               # 루티 JSON 어댑터 (노트북용)
│   ├── storage_routy_adapter.py       # Phase 1 창고 운송 JSON (API용)
│   ├── historical_matcher.py          # 과거 유사사례 매칭 (7개 실제 사건 DB)
│   ├── odcy_recommender.py            # NLIC DB + 카카오 API 창고 탐색
│   ├── visualizer.py                  # 시각화 (LSTM, MRI)
│   └── llm_reporter.py               # Gemini/Claude 자동 보고서 생성
│
├── data/
│   ├── nlic_warehouses.json           # NLIC 부산 물류창고 DB (439개, 좌표 포함)
│   ├── lstm_cache.json                # LSTM 사전계산 캐시 (Render 서버용)
│   ├── kcci_weekly.csv                # KCCI 운임지수 주간
│   ├── gdelt_maritime_monthly.csv     # GDELT 해운 이벤트 월별 집계
│   ├── freight_index/                 # KCCI XLS 원본 파일
│   └── 260414_홈페이지 업데이트_...xlsx  # 2025 부산항 물동량
│
├── scripts/
│   ├── generate_lstm_cache.py         # LSTM 학습 → lstm_cache.json 생성
│   ├── geocode_nlic.py                # NLIC Excel → 지오코딩 → JSON
│   ├── auto_update.py                 # 일별 데이터 자동 갱신
│   └── monthly_update.py              # 월별 데이터 업데이트
│
└── tests/
    ├── test_scenario_engine.py
    ├── test_reorganizer.py
    ├── test_routy_adapter.py
    └── test_real_data_fetcher.py
```

---

## 빠른 시작

### 1. Python 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env` 파일 생성 후 아래 키 입력:

```
KAKAO_REST_API_KEY=...       # 카카오 Local 창고 검색 (무료)
KAKAO_MOBILITY_KEY=...       # 카카오모빌리티 경로 계산 (무료)
NAVER_CLIENT_ID=...          # Naver DataLab (무료)
NAVER_CLIENT_SECRET=...
ECOS_API_KEY=...             # 한국은행 환율 (무료)
GEMINI_API_KEY=...           # LLM 보고서 (무료, 선택)
```

### 3-A. 노트북 실행 (발표용)

```bash
jupyter notebook notebooks/wemeet_v4_main.ipynb
```

### 3-B. FastAPI 백엔드 로컬 실행

```bash
uvicorn api:app --reload --port 8000
# http://localhost:8000/docs  ← Swagger UI
```

### 3-C. React 프론트엔드 로컬 실행

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

`.env` 또는 `frontend/.env.local` 에 다음 추가:
```
VITE_API_BASE_URL=http://localhost:8000
```
(미설정 시 Render 배포 서버로 자동 연결)

---

## 핵심 KPI

| 지표 | 값 | 근거 |
|---|---|---|
| LSTM 검증 MAPE | **9.4%** | 시간순 80/20 분할, 원단위(TEU) 역정규화 후 계산 |
| MRI 가중치 방법 | **하이브리드 엔트로피** | IQR 로버스트 Shannon + 등분 평균 |
| 홍해 유사사례 평균 지연 | **12.3일** | historical_matcher 7개 사건 DB |
| 홍해 유사사례 평균 운임 | **+20.7%** | historical_matcher 7개 사건 DB |
| NLIC 창고 DB | **439개** | 국가물류통합정보센터 부산 등록 창고 |
| 수에즈 통항 감소 | **42~90%** | UNCTAD 2024 실측 데이터 |
| C안 비용 절감 (vs A안) | **약 37%** | CBM=15, 지연=14일 기준 (원화 단가 적용) |

---

## API 키 현황

| API | 용도 | 비용 | 없으면 |
|---|---|---|---|
| 카카오 Local | 창고·ODCY 실시간 탐색 | 무료 (300,000건/일) | NLIC DB 439개로 자동 대체 |
| 카카오모빌리티 | 경로·거리 계산 | 무료 (5,000건/일) | Haversine 추정 대체 |
| ECOS | 환율·유가 | 무료 | frankfurter.app 자동 대체 |
| Naver DataLab | G/D/P 차원 보조 | 무료 | RSS 뉴스만으로 MRI 산출 |
| Google Gemini | LLM 자동 보고서 | 무료 (1,500회/일) | 보고서 기능만 비활성화 |
| BPA | 부산항 물동량 API | 무료 | Excel 파일로 대체 |

---

## 배포 구조

```
로컬 백엔드:   uvicorn api:app --port 8000
로컬 프론트:   cd frontend && npm run dev  (포트 3000)

클라우드 백엔드: Render — https://wemeet-api-dchk.onrender.com
               (GitHub main push → 자동 재배포)
```

- `render.yaml`: Render 배포 설정 (자동 인식)
- `requirements-deploy.txt`: torch 제외 (Render 무료 플랜 2GB 제한 대응)
- `data/lstm_cache.json`: torch 없이도 LSTM 예측 제공 (사전계산 캐시)

> Render 무료 플랜은 **15분 비활성 후 슬립**됩니다. 첫 요청 시 최대 60초 소요.

---

## 주관 기관

- **주관**: 한국해양수산개발원(KMI), 제5차 해운항만물류 인력양성사업
- **연계 기업**: 위밋모빌리티 (Wemet Mobility)
- **대회**: 2026학년도 1학기 기업문제해결 프로젝트 및 공모전
- **루티 연동**: 현재 시뮬레이션 모드 (`integration_status = 'simulation_mode'`)
  → API 발급 시 `'live_api'`로 전환만 하면 즉시 연동 가능한 구조
