이 폴더에 NLIC에서 다운로드한 Excel 파일을 저장하세요.

[ 다운로드 방법 ]
1. https://nlic.go.kr/nlic/seaHarborGtqy.action 접속
2. 항만명: 부산
3. 기간: 2015년 1월 ~ 현재 (연도별 또는 전체 선택)
4. Excel 다운로드
5. 이 폴더(data/nlic_raw/)에 저장

[ 파일 합치기 ]
터미널에서 실행:
  python scripts/monthly_update.py --combine-only

→ data/busan_throughput.csv 자동 생성
→ 이후 노트북 실행 시 실데이터로 자동 적용
