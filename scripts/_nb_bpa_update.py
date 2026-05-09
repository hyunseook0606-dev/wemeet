# -*- coding: utf-8 -*-
"""노트북 BPA 물동량 관련 셀 업데이트"""
import json
from pathlib import Path

NB = Path('notebooks/wemeet_v4_main.ipynb')
with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

# ── Cell 3 (0-2 데이터현황): 자동수집 섹션에 BPA 추가 ────────────────────
# 현재 소스에서 BPA 관련 줄 업데이트
old_sched = "print('  매일  08:30   환율 (frankfurter.app) + 유가 (Yahoo Finance BZ=F)')"
new_sched = (
    "print('  매일  08:30   환율 (frankfurter.app) + 유가 (Yahoo Finance BZ=F)')\n"
    "print('  ※ BPA 물동량: 연도별 API 자동 연결 (BPA_API_KEY 설정됨)')\n"
    "print('    → 1994~2024 연도별 TEU + 계절 분해 → 월별 추정치')"
)

# ── Cell 15 (3-4 거시경제): throughput 소스 레이블 수정 ────────────────────
# 기존: '실데이터 (CSV)' / 'BPA API' / '시뮬'
# 변경: BPA API 성공 시 구체적 설명 추가
old_tp_src = (
    "throughput_src = ('실데이터 (CSV)' if throughput_df is not None and _csv_ok else\n"
    "                  'BPA API' if throughput_df is not None else '시뮬')"
)
new_tp_src = (
    "throughput_src = ('실데이터 (CSV)' if throughput_df is not None and _csv_ok else\n"
    "                  'BPA API (연도별→계절분해)' if throughput_df is not None else '시뮬')"
)

# ── Part 3 Markdown (cell 14): 물동량 설명 업데이트 ─────────────────────
old_step1_note = "각 월의 **실제값**이 입력됩니다. 전체 평균(~1295원)이 아닙니다."
new_step1_note = (
    "각 월의 **실제값**이 입력됩니다. 전체 평균(~1295원)이 아닙니다.\n\n"
    "> **물동량 데이터**: BPA 공식 연도별 합계(1994~2024) × 부산항 계절 패턴 → 월별 추정\n"
    "> 예) 2024년 합계 2,440만 TEU → 월평균 203.4만, 1월 159만(설 저점), 12월 235만(연말 고점)"
)

changes = []

# cell 3 패치
src3 = ''.join(nb['cells'][3]['source'])
new3 = src3.replace(old_sched, new_sched)
if new3 != src3:
    nb['cells'][3]['source'] = new3
    changes.append('cell[3]: BPA 자동수집 설명 추가')

# cell 15 패치
src15 = ''.join(nb['cells'][15]['source'])
new15 = src15.replace(old_tp_src, new_tp_src)
if new15 != src15:
    nb['cells'][15]['source'] = new15
    changes.append('cell[15]: throughput_src 레이블 수정')

# cell 14 패치
src14 = ''.join(nb['cells'][14]['source'])
new14 = src14.replace(old_step1_note, new_step1_note)
if new14 != src14:
    nb['cells'][14]['source'] = new14
    changes.append('cell[14]: 물동량 계절분해 설명 추가')

with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print('=== 노트북 업데이트 ===')
for c in changes: print(f'  {c}')
print(f'변경 없음: {3 - len(changes)}개 셀')
