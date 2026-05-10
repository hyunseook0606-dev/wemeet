# TASKS.md — 프로젝트 현황 및 잔여 작업

> 마지막 업데이트: 2026-05-10
> 전체 개발 완료. 아래는 현황 요약 및 향후 운영 참고용입니다.

---

## 현재 상태 요약

### 완료된 주요 기능

| 기능 | 파일 | 상태 |
|---|---|---|
| MRI 5차원 AHP 산출 | src/mri_engine.py | ✅ 완료 |
| 뉴스 NLP 분류 (한글+영어) | src/nlp_classifier.py | ✅ 완료 |
| 리스크 맥락 제시 (advisory) | src/scenario_engine.py | ✅ 완료 |
| 과거 유사사례 매칭 (7사건) | src/historical_matcher.py | ✅ 완료 |
| LSTM 물동량 예측 | src/lstm_forecaster.py | ✅ 완료 (MAPE 9.4%) |
| NLIC 창고 DB (439개) | data/nlic_warehouses.json | ✅ 완료 |
| 카카오 API 창고 탐색 | src/odcy_recommender.py | ✅ 완료 |
| A/B/C/D 4옵션 비용 산출 | src/option_presenter.py | ✅ 완료 |
| Phase 1/2 루티 JSON 생성 | src/storage_routy_adapter.py | ✅ 완료 |
| FastAPI 백엔드 (8 엔드포인트) | api.py | ✅ 완료 |
| Streamlit 웹앱 (4탭) | app.py | ✅ 완료 |
| 발표용 노트북 (29셀) | notebooks/wemeet_v4_main.ipynb | ✅ 완료 |
| Render 클라우드 배포 | render.yaml | ✅ 배포 완료 |
| Lovable 연동 가이드 | Lovable_연동_개발가이드.docx | ✅ 완료 |

---

## 핵심 설계 결정 사항

### 강제 시나리오 제거 (2026-05-10 확정)
- 기존: MRI → `auto_classify_scenario()` → 강제 시나리오 적용
- 변경: MRI + 뉴스 키워드 → `build_risk_context()` → 참고 정보 제시
- 이유: 최종 결정은 화주의 권한 — 플랫폼은 의사결정 지원만 담당

### NLIC 국가물류통합정보센터 DB 통합 (2026-05-10)
- 부산 등록 창고 439개 지오코딩 완료
- 카카오 API 없어도 정부 공인 데이터로 창고 탐색 가능
- 우선순위: NLIC DB → 카카오 API → 내장 시뮬 9개 (폴백)

### LSTM 캐시 시스템 (2026-05-09)
- Render 서버에 torch 설치 불가 (2GB 초과)
- 로컬 학습 결과를 `data/lstm_cache.json`에 저장 → 서버에서 읽기
- 서버 우선순위: 캐시 → 실시간 학습 → 시뮬값

---

## 운영 중 주기적으로 할 일

### 월간
```bash
# LSTM 재학습 (데이터 업데이트 시)
python scripts/generate_lstm_cache.py
git add data/lstm_cache.json && git commit -m "update lstm cache $(date)" && git push

# 데이터 갱신
python scripts/auto_update.py
```

### NLIC DB 갱신 (분기별 권장)
```bash
# nlic.go.kr에서 새 Excel 다운로드 후:
python scripts/geocode_nlic.py
git add data/nlic_warehouses.json && git commit -m "update nlic db" && git push
```

---

## 현재 배포 현황

| 환경 | URL | 상태 |
|---|---|---|
| FastAPI 서버 | https://wemeet-api-dchk.onrender.com | ✅ 운영 중 |
| GitHub | https://github.com/lwj8840/wemeet-platform | ✅ 최신 |
| Lovable 프론트 | (친구 계정) https://github.com/hyunseook0606-dev/wemeet | ✅ 연동 중 |

> Render 무료 플랜: 15분 미사용 시 슬립. 발표 전 `/api/health` 접속으로 미리 깨울 것.

---

## 잔여 과제 (선택)

- [ ] Lovable 프론트에 카카오맵 JS SDK 연동 (현재는 좌표만 반환)
- [ ] 루티 API 실키 발급 시 `integration_status = 'live_api'` 전환
- [ ] BPA API 키 발급 시 실데이터 전환 (현재 Excel 대체)
