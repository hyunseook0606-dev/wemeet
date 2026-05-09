"""
MRI 기반 과거 유사사례 매칭 엔진
====================================
현재 MRI 수치와 뉴스 NLP 분류 결과를 바탕으로,
과거 해상 리스크 사례 중 가장 유사한 케이스를 찾아
고객에게 "이전에 이런 일이 있었어요" 형식으로 정보를 제공합니다.

설계 철학:
  MRI 수치 하나로 시나리오를 라벨링하면 오류가 발생합니다.
  (예: MRI 0.55가 전쟁일 수도, 기상악화일 수도 있음)
  대신 과거 유사 사례를 제시해 화주가 스스로 판단하도록 지원합니다.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json


# ──────────────────────────────────────────────────────────
# 1. 과거 이벤트 데이터 클래스
# ──────────────────────────────────────────────────────────

@dataclass
class HistoricalEvent:
    """과거 해상 리스크 이벤트 단위"""
    id: str
    name: str
    date: str                          # YYYY-MM-DD
    duration_days: int                 # 이벤트 지속 기간
    mri_peak: float                    # 해당 사건의 MRI 최고점
    mri_range: tuple[float, float]     # MRI 발생 구간 (최소, 최고)
    risk_categories: list[str]         # NLP 분류 카테고리와 매핑
    cause: str                         # 원인 설명
    avg_delay_days: float              # 평균 운항 지연 일수
    avg_freight_increase_pct: float    # 평균 운임 상승률 (%)
    routes_affected: list[str]         # 영향받은 항로
    resolution: str                    # 사태 해소 방식
    source: str = ""                   # 데이터 출처


# ──────────────────────────────────────────────────────────
# 2. 과거 주요 해상 리스크 이벤트 DB
#    (실제 운영 시 DB 또는 JSON 파일로 관리 권장)
# ──────────────────────────────────────────────────────────

HISTORICAL_EVENTS: list[HistoricalEvent] = [
    HistoricalEvent(
        id="HE001",
        name="수에즈 운하 에버기븐 좌초",
        date="2021-03-23",
        duration_days=6,
        mri_peak=0.78,
        mri_range=(0.55, 0.82),
        risk_categories=["지정학분쟁"],
        cause=(
            "초대형 컨테이너선 에버기븐(Ever Given)이 수에즈 운하에 좌초, "
            "전 세계 해상 교역량의 약 12%가 통과하는 핵심 항로를 6일간 완전 봉쇄. "
            "약 400여 척의 선박이 대기하며 전 세계 공급망에 직격탄."
        ),
        avg_delay_days=18,
        avg_freight_increase_pct=34,
        routes_affected=["아시아-유럽", "아시아-지중해", "아시아-미주 동부"],
        resolution="6일 만에 운하 통항 재개. 적체 선박 해소까지 약 3~4주 추가 소요.",
        source="Allianz AGCS 2021 Safety & Shipping Review"
    ),
    HistoricalEvent(
        id="HE002",
        name="홍해 후티 반군 상선 공격 사태",
        date="2023-12-15",
        duration_days=365,
        mri_peak=0.85,
        mri_range=(0.60, 0.88),
        risk_categories=["지정학분쟁"],
        cause=(
            "예멘 후티 반군이 홍해·아덴만을 통과하는 상선을 지속 공격. "
            "MSC, Maersk, CMA CGM 등 주요 선사들이 수에즈 경유 항로를 포기하고 "
            "케이프타운 우회 항로로 전환. 항해 거리 약 3,500해리 증가."
        ),
        avg_delay_days=12,
        avg_freight_increase_pct=22,
        routes_affected=["아시아-유럽", "아시아-지중해", "아시아-미주 동부"],
        resolution="케이프타운 우회 항로가 사실상 표준화됨. 운임은 고점 대비 부분 안정화.",
        source="Drewry World Container Index / KCCI 2024"
    ),
    HistoricalEvent(
        id="HE003",
        name="미중 관세 전쟁 1단계",
        date="2019-05-10",
        duration_days=90,
        mri_peak=0.58,
        mri_range=(0.35, 0.62),
        risk_categories=["관세정책"],
        cause=(
            "미국이 2,000억 달러 규모 중국산 수입품에 관세 25% 부과. "
            "수출 기업들의 선적 전·후 물동량 급변동, 선복 예측 불확실성 심화. "
            "한국 수출기업도 간접 영향권 진입."
        ),
        avg_delay_days=4,
        avg_freight_increase_pct=9,
        routes_affected=["아시아-미주 서부", "한국-미주"],
        resolution="2020년 1단계 무역합의 서명으로 일부 관세 완화.",
        source="WTO 무역통계 2019 / KCCI 2019"
    ),
    HistoricalEvent(
        id="HE004",
        name="COVID-19 글로벌 항만 혼란",
        date="2020-03-01",
        duration_days=540,
        mri_peak=0.92,
        mri_range=(0.70, 0.95),
        risk_categories=["항만파업", "기상재해"],
        cause=(
            "전 세계 동시 봉쇄로 항만 인력 부족과 컨테이너 수급 불균형 동시 발생. "
            "중국 공장 가동 중단 → 급격한 물동량 감소 → 역반등으로 선복 부족 극심. "
            "부산항을 포함한 아시아 주요 항만 처리량 30~50% 감소."
        ),
        avg_delay_days=21,
        avg_freight_increase_pct=85,
        routes_affected=["전 노선"],
        resolution="백신 보급 및 항만 운영 점진적 정상화 (2022년 하반기 완료).",
        source="UNCTAD 2021~2022 / 한국해양수산개발원(KMI)"
    ),
    HistoricalEvent(
        id="HE005",
        name="태풍 힌남노 부산항 직격",
        date="2022-09-06",
        duration_days=5,
        mri_peak=0.68,
        mri_range=(0.45, 0.72),
        risk_categories=["기상재해"],
        cause=(
            "역대급 초강력 태풍 힌남노가 한반도를 직격. "
            "부산항 컨테이너 야드 일시 봉쇄, 하역 작업 전면 중단. "
            "CY 장치 화물의 이동 불가로 출항 일정 전면 재조정."
        ),
        avg_delay_days=7,
        avg_freight_increase_pct=6,
        routes_affected=["부산 출항 전 노선"],
        resolution="태풍 통과 후 48시간 내 항만 운영 정상화.",
        source="부산항만공사(BPA) 2022 운영보고서"
    ),
    HistoricalEvent(
        id="HE006",
        name="상하이 코로나 봉쇄 (2022)",
        date="2022-03-28",
        duration_days=65,
        mri_peak=0.77,
        mri_range=(0.58, 0.80),
        risk_categories=["항만파업"],
        cause=(
            "중국 제로코로나 정책으로 세계 최대 컨테이너항인 상하이항 기능 급감. "
            "주변 닝보·칭다오항으로 화물 분산, 한국 경유 물동량도 급변동. "
            "총 65일 봉쇄로 전 세계 공급망 누적 피해 3,000억 달러 추정."
        ),
        avg_delay_days=14,
        avg_freight_increase_pct=18,
        routes_affected=["아시아 역내", "아시아-유럽", "아시아-미주"],
        resolution="봉쇄 해제(5월 말) 후 적체 해소까지 6~8주 추가 소요.",
        source="S&P Global Market Intelligence 2022"
    ),
    HistoricalEvent(
        id="HE007",
        name="미국 서부항만 ILWU 파업 협상 위기",
        date="2023-06-01",
        duration_days=30,
        mri_peak=0.55,
        mri_range=(0.40, 0.60),
        risk_categories=["항만파업"],
        cause=(
            "ILWU(국제항만창고노조)와 PMA 간 임금 협상 결렬 우려로 "
            "미국 서부 29개 항만 파업 임박. "
            "화주들이 LA/롱비치 → 뉴욕/조지아 동부 항만으로 화물 전환 시도."
        ),
        avg_delay_days=8,
        avg_freight_increase_pct=12,
        routes_affected=["아시아-미주 서부"],
        resolution="연방 조정위원회 중재로 잠정 합의, 전면 파업 회피.",
        source="Journal of Commerce 2023 / USDA 공급망 보고서"
    ),
]


# ──────────────────────────────────────────────────────────
# 3. 유사 사례 매칭 함수
# ──────────────────────────────────────────────────────────

def find_similar_events(
    current_mri: float,
    detected_categories: list[str],
    top_k: int = 3,
) -> list[dict]:
    """
    현재 MRI 수치와 뉴스 NLP 분류 카테고리를 기반으로
    과거 유사 사례를 유사도 순(오름차순)으로 반환합니다.

    유사도 점수 = MRI 피크 거리 + 범위 밖 패널티 + 카테고리 불일치 패널티
    (낮을수록 더 유사)

    Parameters
    ----------
    current_mri : float
        현재 산출된 MRI 값 (0.0 ~ 1.0)
    detected_categories : list[str]
        NLP 분류기가 감지한 뉴스 카테고리 리스트
    top_k : int
        반환할 유사 사례 수 (기본 3)

    Returns
    -------
    list[dict]
        유사도 순 정렬된 이벤트 정보 딕셔너리 리스트
    """
    scored = []
    for event in HISTORICAL_EVENTS:
        mri_distance = abs(current_mri - event.mri_peak)
        in_range     = event.mri_range[0] <= current_mri <= event.mri_range[1]
        range_penalty   = 0.0 if in_range else 0.20
        cat_overlap     = len(set(detected_categories) & set(event.risk_categories))
        cat_penalty     = 0.0 if cat_overlap > 0 else 0.15

        score = mri_distance + range_penalty + cat_penalty
        scored.append({
            "event": event,
            "similarity_score": score,
            "mri_distance": mri_distance,
            "in_range": in_range,
            "category_match": cat_overlap > 0,
        })

    scored.sort(key=lambda x: x["similarity_score"])

    results = []
    for rank, item in enumerate(scored[:top_k], 1):
        ev = item["event"]
        results.append({
            "rank":                     rank,
            "id":                       ev.id,
            "name":                     ev.name,
            "date":                     ev.date,
            "duration_days":            ev.duration_days,
            "mri_peak":                 ev.mri_peak,
            "cause":                    ev.cause,
            "avg_delay_days":           ev.avg_delay_days,
            "avg_freight_increase_pct": ev.avg_freight_increase_pct,
            "routes_affected":          ev.routes_affected,
            "resolution":               ev.resolution,
            "source":                   ev.source,
            "similarity_score":         round(item["similarity_score"], 3),
            "category_match":           item["category_match"],
            "in_mri_range":             item["in_range"],
        })
    return results


# ──────────────────────────────────────────────────────────
# 4. 고객 메시지 포매터
# ──────────────────────────────────────────────────────────

def format_customer_message(
    current_mri: float,
    similar_events: list[dict],
) -> str:
    """
    화주 홈페이지에 노출할 한국어 설명 메시지를 생성합니다.
    '이전에 이런 일이 있었어요' 형식.
    """
    lines = [
        f"📊 현재 해상 리스크 지수 (MRI): {current_mri:.2f}",
        "",
        "━━━ 과거 유사 사례 분석 ━━━",
        "현재와 비슷한 수치가 기록됐던 과거 사례를 바탕으로",
        "참고 정보를 제공합니다.",
        "",
    ]

    for ev in similar_events:
        match_label = "✅ 리스크 유형 일치" if ev["category_match"] else "🔵 MRI 수치 유사"
        lines.append(
            f"[{ev['rank']}위] {ev['name']} ({ev['date'][:4]}년) ── {match_label}"
        )
        lines.append(f"   📌 원인: {ev['cause'][:100]}...")
        lines.append(f"   ⏱  평균 지연: {ev['avg_delay_days']}일")
        lines.append(f"   💰 운임 상승: +{ev['avg_freight_increase_pct']}%")
        lines.append(f"   🚢 영향 항로: {', '.join(ev['routes_affected'])}")
        lines.append(f"   🔚 해소 방식: {ev['resolution']}")
        lines.append(f"   📖 출처: {ev['source']}")
        lines.append("")

    if similar_events:
        avg_delay   = sum(e["avg_delay_days"] for e in similar_events) / len(similar_events)
        avg_freight = sum(e["avg_freight_increase_pct"] for e in similar_events) / len(similar_events)
        lines += [
            "━━━ 유사 사례 평균 통계 ━━━",
            f"  • 평균 지연:    {avg_delay:.1f}일",
            f"  • 평균 운임 상승: +{avg_freight:.1f}%",
            "",
        ]

    lines += [
        "⚠️  본 정보는 과거 사례를 기반으로 한 참고 자료입니다.",
        "    실제 상황은 다를 수 있으며, 포워더와 직접 확인을 권장합니다.",
    ]
    return "\n".join(lines)


def to_json(similar_events: list[dict]) -> str:
    """API 응답용 JSON 직렬화"""
    return json.dumps(similar_events, ensure_ascii=False, indent=2, default=str)
