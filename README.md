# 해상 리스크 대응형 공동 물류 운영 플랫폼

> 위밋모빌리티 × 한국해양수산개발원(KMI) — 2026년 1학기 기업문제해결 프로젝트

해상 공급망 리스크 발생 시 중소 수출기업에게 **과거 유사사례 기반 참고 정보**를 제시하고,
항만 주변 창고·ODCY를 자동 탐색해 4가지 대응 옵션을 제안하며,
화주가 선택한 결과를 위밋 루티/루티프로 입력 JSON으로 변환하는 의사결정 지원 플랫폼

---

## 플랫폼 흐름 (4단계)

```
Step 1  화주 입력        화물 종류·CBM·항로·납기·집화일 등록
   ↓
Step 2  MRI 분석 + 리스크 맥락 제시
                         실시간 뉴스 → MRI 산출 → 등급 판정
                         현재 이슈 자동 요약 (뉴스 키워드 기반)
                         과거 유사사례 평균 지연·운임 참고 제공
                         LSTM 부산항 물동량 3개월 예측
   ↓
Step 3  창고 추천         MRI ≥ 0.5 시 활성화
(MRI ≥ 0.5)              NLIC 정부DB(439개) + 카카오 API 실시간 병행 탐색
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
| 해상 가시성·ETA 예측 | ✅ 강점 (트레드링스, Flexport) | △ 보완재 포지셔닝 |
| **선제적 리스크 맥락 제시** | ❌ | ✅ MRI 5차원 AHP + 과거 유사사례 평균 참고 |
| **항만 창고 자동 탐색** | ❌ | ✅ NLIC 정부DB 439개 + 카카오 실데이터 |
| **국내 내륙 배차 통합** | ❌ | ✅ 루티(ROOUTY) JSON 자동 생성 |
| **과거 유사사례 인사이트** | ❌ | ✅ historical_matcher (7개 실제 사건 DB) |

---

## MRI 등급 및 리스크 맥락

플랫폼은 MRI 점수와 현재 뉴스 키워드를 바탕으로 화주에게 **참고 정보**를 제시합니다.
강제 시나리오 없음 — 최종 판단은 화주에게 있습니다.

| MRI 등급 | 범위 | 현재 이슈 예시 | 창고 추천 활성화 |
|---|---|---|---|
| 🟢 정상 | < 0.3 | 현재 주요 해상 리스크 없음 | X |
| 🟡 주의 | 0.3 ~ 0.5 | 항만 혼잡·운임 변동 가능성 | X |
| 🟠 경계 | 0.5 ~ 0.7 | 태풍·기상 악화로 항로 위험 | O |
| 🔴 위험 | ≥ 0.7 | 홍해·수에즈 관련 지정학 리스크 상승 | O |

**과거 유사사례 기반 참고값** (확정값 아님):
- 지정학 분쟁 유사 3건 평균: 지연 12.3일, 운임 +20.7%
- 기상 악화 유사 3건 평균: 지연 6.3일, 운임 +5.3%

---

## 프로젝트 구조

```
vs code/
├── CLAUDE.md                          # Claude Code 컨텍스트
├── README.md                          # 이 파일
├── PROJECT_SPEC.md                    # 상세 명세
├── SETUP_GUIDE.md                     # 설치·실행 가이드
├── TASKS.md                           # 작업 목록
├── requirements.txt                   # Python 의존성 (로컬)
├── requirements-deploy.txt            # Python 의존성 (Render 배포용, torch 제외)
├── render.yaml                        # Render 클라우드 배포 설정
├── .env                               # API 키 (Git 제외)
├── .env.example                       # 환경변수 예시
│
├── api.py                             # ★ FastAPI 백엔드 (Lovable 연동)
├── app.py                             # Streamlit 웹앱 (4탭)
│
├── notebooks/
│   └── wemeet_v4_main.ipynb           # 발표용 메인 노트북 (29셀)
│
├── src/
│   ├── config.py                      # AHP 가중치, 키워드, 항로 정보
│   ├── data_loader.py                 # KCCI / 부산항 BPA / ECOS 로더
│   ├── real_data_fetcher.py           # RSS 뉴스, 유가, 환율 실시간 수집
│   ├── freight_index_loader.py        # KCCI XLS 파일 파서
│   ├── nlp_classifier.py              # 키워드 사전 분류기 (한글+영어)
│   ├── mri_engine.py                  # MRI 5차원 AHP 산출
│   ├── lstm_forecaster.py             # LSTM 부산항 물동량 예측
│   ├── scenario_engine.py             # ★ 리스크 맥락 구성 + (시뮬용) 시나리오 분류
│   ├── reorganizer.py                 # 권역 단위 운영 재조정 (Tab4 시뮬용)
│   ├── routy_adapter.py               # 루티 JSON 어댑터 (Tab4 시뮬용)
│   ├── historical_matcher.py          # ★ 과거 유사사례 매칭 (7개 실제 사건 DB)
│   ├── odcy_recommender.py            # ★ NLIC DB + 카카오 API 창고 탐색
│   ├── option_presenter.py            # ★ A/B/C/D 4가지 옵션 비용 산출
│   ├── storage_routy_adapter.py       # ★ Phase 1/2 창고 운송 JSON
│   ├── visualizer.py                  # 시각화 (LSTM, MRI)
│   └── llm_reporter.py               # Gemini/Claude 자동 보고서 생성
│
├── data/
│   ├── nlic_warehouses.json           # ★ NLIC 부산 물류창고 DB (439개, 좌표 포함)
│   ├── lstm_cache.json                # LSTM 사전계산 캐시 (Render 서버용)
│   ├── kcci_weekly.csv                # KCCI 운임지수
│   ├── freight_index/                 # KCCI XLS 원본 파일
│   └── 260414_홈페이지 업데이트_...xlsx  # 2025 부산항 물동량
│
├── scripts/
│   ├── generate_lstm_cache.py         # LSTM 학습 → lstm_cache.json 생성
│   ├── geocode_nlic.py                # NLIC Excel → 지오코딩 → nlic_warehouses.json
│   ├── auto_update.py                 # 일별 데이터 자동 갱신
│   ├── _make_lovable_guide.py         # Lovable 가이드 DOCX 생성
│   └── _make_render_guide.py          # Render 배포 가이드 DOCX 생성
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

```powershell
Copy-Item .env.example .env   # Windows PowerShell
```

최소 필요 키: `GEMINI_API_KEY` (무료), `KAKAO_REST_API_KEY` (무료)

### 3-A. 노트북 실행 (발표용)

```bash
jupyter notebook notebooks/wemeet_v4_main.ipynb
```

셀 순서대로 실행. cell[06]에서 화주 정보 수정.

### 3-B. Streamlit 웹앱 실행

```bash
streamlit run app.py
```

`http://localhost:8501` 접속.

### 3-C. FastAPI 백엔드 실행 (Lovable 연동)

```bash
uvicorn api:app --reload --port 8000
```

`http://localhost:8000/docs` 에서 Swagger UI로 API 테스트.

### 4. LSTM 캐시 생성 (서버 배포 전)

```bash
python scripts/generate_lstm_cache.py
git add data/lstm_cache.json && git commit -m "update lstm cache" && git push
```

### 5. 단위 테스트

```bash
pytest tests/ -v
```

---

## 핵심 KPI

| 지표 | 값 | 근거 |
|---|---|---|
| LSTM 검증 MAPE | **9.4%** | 시간순 80/20 분할, 원단위(TEU) 역정규화 |
| 홍해 유사사례 평균 지연 | **12.3일** | historical_matcher 7개 사건 DB 평균 |
| 홍해 유사사례 평균 운임 | **+20.7%** | historical_matcher 7개 사건 DB 평균 |
| NLIC 창고 DB | **439개** | 국가물류통합정보센터 부산 등록 창고 |
| 수에즈 통항 감소 | **42~90%** | UNCTAD 2024 실측 데이터 |
| AHP 일관성 비율 | **CR=3.1%** | < 10% 기준 통과 |

---

## API 키 현황

| API | 용도 | 비용 | 없으면 |
|---|---|---|---|
| Google Gemini | LLM 자동 보고서 | 무료 (1,500회/일) | 보고서 기능 비활성화 |
| 카카오 Local | 창고·ODCY 실시간 탐색 | 무료 (300,000건/일) | NLIC DB 439개 사용 |
| 카카오모빌리티 | 경로·거리 계산 | 무료 (5,000건/일) | Haversine 추정 대체 |
| ECOS | 환율·유가·GDP | 무료 | Yahoo Finance 자동 대체 |
| BPA | 부산항 물동량 | 무료 | Excel + 계절분해 대체 |

---

## 배포 구조

```
로컬:    uvicorn api:app --port 8000  +  streamlit run app.py
서버:    Render (Singapore) — https://wemeet-api-dchk.onrender.com
프론트:  Lovable (React) — VITE_API_BASE_URL = Render URL
```

- `render.yaml`: 서버 배포 설정 (자동 인식)
- `requirements-deploy.txt`: torch 제외 버전 (Render 무료 플랜 용량 제한)
- `data/lstm_cache.json`: torch 없이도 LSTM 결과 제공 (사전계산 캐시)

---

## 주관 기관

- **주관**: 한국해양수산개발원(KMI), 제5차 해운항만물류 인력양성사업
- **연계 기업**: 위밋모빌리티 (Wemet Mobility)
- **루티 연동**: 현재 시뮬레이션 모드 (`integration_status = 'simulation_mode'`)
  → API 발급 시 `'live_api'`로 전환만 하면 즉시 연동 가능한 구조
