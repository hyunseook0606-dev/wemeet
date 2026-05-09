이 폴더에 KCCI/KUWI/KUEI 운임지수 XLS 파일을 저장하세요.

[ 지원 파일 형식 ]
  .xls, .xlsx  (Excel 97-2003 또는 최신)

[ 인식되는 지수 ]
  KCCI  한국컨테이너운임종합지수
  KUWI  한국컨테이너운임가중지수
  KUEI  한국컨테이너운임등락지수
  + 항로별 세부지수 (부산-LA, 부산-로테르담 등)

[ 파일명 규칙 ]
  파일명은 자유롭게 설정 가능
  예: kcci_2022q4.xls, freight_2023.xlsx 등

[ 합치기 실행 ]
  터미널에서:
    python scripts/auto_update.py --combine-freight

  → data/kcci_weekly.csv 자동 생성
  → 이후 노트북·앱에서 실데이터로 자동 적용

[ 주간 자동 갱신 ]
  PowerShell에서:
    .\scripts\setup_scheduler.ps1

  → 매주 월요일 09:00 자동 합치기 실행
