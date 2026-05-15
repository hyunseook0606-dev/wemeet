"""
scenario_cost.py — 해상 리스크 대응 시나리오 A/B/C 비용 비교 엔진
=================================================================

[시나리오 정의]
  A (무대응 → ODCY 이송)
      화물이 항만 CY에 반입 → 무료 장치기간(기본 5일) 소진 → ODCY로 이송
      ODCY 보관 후 선적 재개 시 반출
      비용: ODCY 이송비(고정) + ODCY 일일 보관료 × 초과 일수

  B (무대응 → ODCY 자리 없음 → CY 계속 장치)
      A와 동일하게 시작하나, ODCY 자리가 없어 CY에 계속 장치
      CY 초과 장치료(Demurrage)가 ODCY보다 훨씬 비쌈
      비용: CY 초과 장치료 × 초과 일수 (가장 비쌈)

  C (플랫폼 탐지 → 외부 보세창고 사전 이송) ← 권장
      MRI 이상 탐지 → 화물을 CY 반입 전에 항만 인근 보세창고로 선이송
      선적 재개 시 보세창고 → CY 이송
      비용: 보세창고 일일 보관료 × 전체 지연일 (가장 저렴)

[단가 기준 — 실제 부산항 주변 업체 확인치 (2024 기준)]
  ODCY 보관:       10,000 원/CBM/일
  외부 보세창고:    4,000 원/CBM/일
  CY 초과 장치료:  30,000 원/CBM/일  (부산항 표준 초과장치료 기준)
  CY 무료 장치기간: 5일 (부두 반입 후 기준, 항만사별 차이 있음)
  ODCY 이송비:     150,000 원/건 (CY→ODCY 컨테이너 트레일러 기준)
  보세창고 이송비:  100,000 원/건 (출발지→창고 추가 거리 기준)

출처:
  - 부산항만공사(BPA) ODCY 요금 안내 (2024)
  - 관세청 보세창고 임대료 고시 (2024)
  - 부산항 선사별 무료장치기간 기준
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ── 단가 상수 (원/CBM/일 또는 원/건) ─────────────────────────────────────────

CY_FREE_DAYS        = 5          # CY 무료 장치기간 (일)
ODCY_DAILY_KRW      = 10_000    # ODCY 보관료 (원/CBM/일)
BONDED_DAILY_KRW    = 4_000     # 외부 보세창고 보관료 (원/CBM/일)
CY_DEMURRAGE_KRW    = 30_000    # CY 초과 장치료 Demurrage (원/CBM/일)
ODCY_TRANSFER_KRW   = 150_000   # CY→ODCY 이송비 (원/건 고정)
BONDED_TRANSFER_KRW = 100_000   # 출발지→보세창고 추가 이송비 (원/건 고정)


@dataclass
class ScenarioCost:
    """시나리오 1건 비용 명세"""
    label:            str         # 'A', 'B', 'C'
    name:             str
    description:      str

    free_days_used:   int   = 0   # 무료 장치 사용 일수
    paid_days:        int   = 0   # 유료 보관 일수
    daily_rate_krw:   int   = 0   # 일일 단가 (원/CBM)
    cbm:              float = 0.0

    storage_krw:      int   = 0   # 보관료 합계
    transfer_krw:     int   = 0   # 이송비
    total_krw:        int   = 0   # 합계

    recommend:        bool  = False   # 권장 여부
    note:             str   = ""


def calc_scenarios(
    cbm:          float,
    delay_days:   int,
    free_days:    int = CY_FREE_DAYS,
    odcy_daily:   int = ODCY_DAILY_KRW,
    bonded_daily: int = BONDED_DAILY_KRW,
    cy_demurrage: int = CY_DEMURRAGE_KRW,
) -> list[ScenarioCost]:
    """
    동일 화물(cbm)·동일 지연(delay_days) 기준 A/B/C 시나리오 비용 산출.

    Parameters
    ----------
    cbm         : 화물 부피 (CBM)
    delay_days  : 총 예상 지연 일수
    free_days   : CY 무료 장치기간 (기본 5일)
    odcy_daily  : ODCY 일일 보관료 (원/CBM/일)
    bonded_daily: 외부 보세창고 일일 보관료 (원/CBM/일)
    cy_demurrage: CY 초과 장치료 (원/CBM/일)

    Returns
    -------
    list[ScenarioCost] : [A, B, C] 순서
    """
    paid_days    = max(0, delay_days - free_days)   # 무료 기간 이후 유료 일수

    # ── 시나리오 A: 무대응 → ODCY 이송 ──────────────────────────────────────
    a_storage  = int(paid_days * cbm * odcy_daily)
    a_transfer = ODCY_TRANSFER_KRW if paid_days > 0 else 0
    a_total    = a_storage + a_transfer
    A = ScenarioCost(
        label="A", name="무대응 — ODCY 이송",
        description=(
            f"CY 반입 → 무료 {free_days}일 소진 → ODCY 이송 → 선적 재개 시 반출\n"
            f"ODCY 보관: {paid_days}일 × {cbm:.1f}CBM × {odcy_daily:,}원 = {a_storage:,}원\n"
            f"ODCY 이송비 (고정): {a_transfer:,}원"
        ),
        free_days_used=min(free_days, delay_days),
        paid_days=paid_days,
        daily_rate_krw=odcy_daily,
        cbm=cbm,
        storage_krw=a_storage,
        transfer_krw=a_transfer,
        total_krw=a_total,
        recommend=False,
        note="무료 장치기간 내 선적 재개 시 비용 없음. 초과 시 ODCY 이송 발생.",
    )

    # ── 시나리오 B: 무대응 → ODCY 자리 없음 → CY 계속 장치 ─────────────────
    b_storage  = int(paid_days * cbm * cy_demurrage)
    b_transfer = 0   # 이송 없이 CY에 계속 있음
    b_total    = b_storage + b_transfer
    B = ScenarioCost(
        label="B", name="무대응 — CY 계속 장치 (ODCY 만석)",
        description=(
            f"CY 반입 → 무료 {free_days}일 소진 → ODCY 만석으로 CY 계속 장치\n"
            f"CY 초과 장치료: {paid_days}일 × {cbm:.1f}CBM × {cy_demurrage:,}원 = {b_storage:,}원\n"
            f"⚠️ CY 초과 장치료는 ODCY 대비 {cy_demurrage//odcy_daily}배 고가"
        ),
        free_days_used=min(free_days, delay_days),
        paid_days=paid_days,
        daily_rate_krw=cy_demurrage,
        cbm=cbm,
        storage_krw=b_storage,
        transfer_krw=b_transfer,
        total_krw=b_total,
        recommend=False,
        note="항만 성수기·리스크 발생 시 ODCY 만석 가능. 최악의 시나리오.",
    )

    # ── 시나리오 C: 플랫폼 탐지 → 외부 보세창고 선이송 ─────────────────────
    c_storage  = int(delay_days * cbm * bonded_daily)   # 무료 기간 없음 (CY 미반입)
    c_transfer = BONDED_TRANSFER_KRW
    c_total    = c_storage + c_transfer
    C = ScenarioCost(
        label="C", name="★ 플랫폼 추천 — 외부 보세창고 선이송",
        description=(
            f"MRI 이상 탐지 → 출발지에서 직접 보세창고 이송 (CY 미반입)\n"
            f"보세창고 보관: {delay_days}일 × {cbm:.1f}CBM × {bonded_daily:,}원 = {c_storage:,}원\n"
            f"이송비 (고정): {c_transfer:,}원\n"
            f"✅ 무료장치기간 없지만 일일 단가가 ODCY 대비 {odcy_daily//bonded_daily}배↓"
        ),
        free_days_used=0,
        paid_days=delay_days,
        daily_rate_krw=bonded_daily,
        cbm=cbm,
        storage_krw=c_storage,
        transfer_krw=c_transfer,
        total_krw=c_total,
        recommend=True,
        note=f"A 대비 {a_total - c_total:,}원 절약 ({(a_total - c_total) / a_total * 100:.0f}%) — 지연일이 길수록 격차 증가.",
    )

    return [A, B, C]


def print_scenario_table(scenarios: list[ScenarioCost], title: str = "") -> None:
    """콘솔 출력용 비교표"""
    if title:
        print(f"\n{'═'*62}")
        print(f"  {title}")
        print(f"{'═'*62}")

    baseline = next((s for s in scenarios if s.label == 'A'), scenarios[0])

    print(f"  {'시나리오':<28} {'보관료':>9} {'이송비':>8} {'합계':>10} {'A대비':>9}")
    print(f"  {'─'*60}")
    for s in scenarios:
        diff = baseline.total_krw - s.total_krw
        diff_str = (f"−{diff:,}↓절약" if diff > 0
                    else (f"+{abs(diff):,}↑추가" if diff < 0 else "기준"))
        star = "★ " if s.recommend else "  "
        print(f"  {star}{s.label}안 {s.name[:22]:<22} "
              f"{s.storage_krw:>9,}  {s.transfer_krw:>7,}  "
              f"{s.total_krw:>9,}  {diff_str:>9}")

    print(f"  {'─'*60}")
    rec = next((s for s in scenarios if s.recommend), None)
    if rec:
        diff = baseline.total_krw - rec.total_krw
        pct  = diff / baseline.total_krw * 100 if baseline.total_krw else 0
        print(f"\n  ★ 권장: {rec.label}안 — A안 대비 {diff:,}원 절약 ({pct:.0f}%)")
        print(f"  ※ 단, 플랫폼을 통한 보세창고 선이송이 가능한 경우에 한함.")


def scenario_to_dict(s: ScenarioCost) -> dict:
    """노트북 시각화용 dict 변환"""
    return {
        "label": s.label, "name": s.name,
        "storage_krw": s.storage_krw, "transfer_krw": s.transfer_krw,
        "total_krw": s.total_krw, "recommend": s.recommend,
        "note": s.note,
    }
