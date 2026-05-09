# 설치 및 실행 가이드

> 처음 시작하는 분도 이 순서대로 따라오면 됩니다. (소요 시간: 약 30분)

---

## 0. 사전 준비

| 필요 항목 | 확인 방법 | 다운로드 |
|---|---|---|
| Python 3.10+ | `python --version` | python.org |
| VS Code (권장) | — | code.visualstudio.com |

---

## 1. 프로젝트 폴더 열기

VS Code → 파일 → 폴더 열기 → `vs code/vs code/` 선택

---

## 2. Python 패키지 설치

터미널(PowerShell)에서:

```bash
pip install -r requirements.txt
```

> **PyTorch CPU 전용 설치** (GPU 없는 일반 PC):
> ```bash
> pip install torch --index-url https://download.pytorch.org/whl/cpu
> ```

---

## 3. API 키 설정

```powershell
Copy-Item .env.example .env
```

`.env` 파일을 열고 키를 입력합니다.

### 필수 (무료)

**Google Gemini** — LLM 자동 보고서 생성
1. https://aistudio.google.com 접속
2. 구글 계정 로그인 → "Get API key" → 새 키 생성
3. `.env`에 `GEMINI_API_KEY=발급받은키` 입력

**카카오** — 창고·ODCY 탐색 + 경로 계산
1. https://developers.kakao.com 접속
2. 카카오 계정 로그인 → 내 애플리케이션 → 애플리케이션 추가
3. 앱 이름 입력 → 저장 → 앱 선택 → 앱 키 → **REST API 키** 복사
4. `.env`에 아래 두 줄 입력 (동일한 키):
   ```
   KAKAO_REST_API_KEY=복사한키
   KAKAO_MOBILITY_KEY=복사한키
   ```

### 선택 (없으면 자동 대체)

- `ECOS_API_KEY`: 한국은행 공식 환율·유가 (없으면 Yahoo Finance로 대체)
- `BPA_API_KEY`: 부산항 실데이터 (없으면 Excel+계절분해로 대체)

---

## 4. 실행 방법

### 4-A. 노트북 (발표 시연용) — 권장

```bash
jupyter notebook
```

`notebooks/wemeet_v4_main.ipynb` 열기 → **셀 순서대로 실행**

> cell[06]의 `SHIPPER_INPUT`에서 화주 정보를 수정하면
> 이후 모든 분석(MRI, 창고 추천, 옵션 비교)이 자동으로 반영됩니다.

### 4-B. Streamlit 웹앱

```bash
streamlit run app.py
```

`http://localhost:8501` 접속. 4개 탭으로 구성됩니다.

### 4-C. FastAPI 백엔드 (Lovable 연동)

```bash
uvicorn api:app --reload --port 8000
```

`http://localhost:8000/docs` 에서 Swagger UI로 API 테스트 가능.

---

## 5. 단위 테스트

```bash
pytest tests/ -v
```

---

## 6. Lovable 프론트엔드 연동

`Lovable_연동_개발가이드.docx` 참조. FastAPI 백엔드 실행 후 진행합니다.

---

## 자주 발생하는 오류

| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError: No module named 'src'` | 노트북 cell[02] 먼저 실행 |
| LSTM 결과 없음 | `pip install torch` 후 재시작 |
| 창고 0건 탐색 | 카카오 키 없으면 시뮬 DB 자동 사용 — 정상 |
| `FileNotFoundError: data/...png` | ROOT 경로 오류 — `ROOT / 'data' / '...'` 확인 |
