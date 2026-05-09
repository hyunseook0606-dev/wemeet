"""
창고·ODCY 운송용 루티 JSON 어댑터
====================================
해상 리스크로 선적이 지연될 때,
화주의 화물을 항만 인근 창고·ODCY까지 운송하는
루티(ROOUTY) API 입력용 JSON을 생성합니다.

운송 시나리오 2단계:
  Phase 1 (지연 발생 시): 출발지 → 추천 창고·ODCY       ← 이 파일이 담당
  Phase 2 (선적 재개 시): 창고·ODCY → 항만 CY           ← 추후 Phase 2 JSON 별도 생성
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
import json
import uuid


# ──────────────────────────────────────────────────────────
# 1. 루티 Phase 1 JSON 생성 (출발지 → 창고)
# ──────────────────────────────────────────────────────────

def generate_storage_routy_json(
    shipment_id: str,
    company: str,
    region: str,
    cargo_type: str,
    cbm: float,
    cold_chain: bool,
    hazmat: bool,
    origin_address: str,
    original_port: str,
    original_pickup_date: str,     # YYYY-MM-DD
    mri_current: float,
    delay_reason: str,
    recommended_warehouse: dict,   # odcy_recommender.recommend_storage() 종합추천 1위
    phase2_ready_date: Optional[str] = None,  # 선적 재개 예정일 (없으면 미정)
) -> dict:
    """
    화주 화물을 추천 창고까지 운송하는 루티 Phase 1 JSON을 생성합니다.

    Parameters
    ----------
    recommended_warehouse : odcy_recommender.recommend_storage() 반환값에서
                            recommendations["comprehensive"][0] 항목

    Returns
    -------
    dict : 루티 API POST /v1/dispatch/execute 입력 스펙과 동일한 구조
    """
    now = datetime.now()
    eg_id = f"EG-{now.strftime('%Y%m%d')}-STORAGE-{shipment_id}"

    # 픽업 일정: 원래 픽업일 기준, 오늘부터 최대 2일 내
    pickup_dt = datetime.strptime(original_pickup_date, "%Y-%m-%d")
    adjusted_pickup = max(now, pickup_dt - timedelta(days=1))

    wh = recommended_warehouse

    return {
        "execution_group_id":   eg_id,
        "generated_at":         now.isoformat(timespec="seconds"),
        "phase":                "PHASE1_TO_STORAGE",
        "phase_description":    "해상 리스크 발생 → 출발지에서 항만 인근 창고·ODCY로 임시 운송",

        "risk_context": {
            "mri_current":      round(mri_current, 3),
            "delay_reason":     delay_reason,
            "original_port":    original_port,
            "original_pickup":  original_pickup_date,
            "decision":         "HOLDBACK_TO_STORAGE",
        },

        "shipment": {
            "shipment_id":      shipment_id,
            "company":          company,
            "region":           region,
            "cargo_type":       cargo_type,
            "cbm":              cbm,
            "cold_chain":       cold_chain,
            "hazmat":           hazmat,
            "origin_address":   origin_address,
        },

        "dispatch": {
            "origin": {
                "name":    f"{company} 출고지",
                "address": origin_address,
            },
            "destination": {
                "name":    wh.get("name", ""),
                "address": wh.get("address", ""),
                "phone":   wh.get("phone", ""),
                "type":    wh.get("type", "창고"),
                "lat":     None,   # ROOUTY가 주소로 geocoding 수행
                "lng":     None,
            },
            "adjusted_pickup":  adjusted_pickup.strftime("%Y-%m-%d"),
            "action":           "DELIVER_TO_STORAGE",
            "distance_km":      wh.get("distance_km"),
            "duration_min":     wh.get("duration_min"),
            "special_handling": {
                "cold_chain":   cold_chain,
                "hazmat":       hazmat,
                "notes":        wh.get("special_notes", ""),
            },
        },

        "phase2_plan": {
            "ready_date":   phase2_ready_date or "TBD (선적 재개 시 자동 갱신)",
            "action":       "DELIVER_TO_CY",
            "destination":  original_port,
            "note":         "선적 일정 확정 후 Phase 2 JSON 자동 생성 예정",
        },

        "meta": {
            "note":               "위밋 플랫폼 → 루티 API 입력 스펙 (Phase 1: 창고 임시 보관)",
            "integration_status": "simulation_mode",
            "next_step_api":      "POST /v1/dispatch/execute",
            "routy_version":      "v1",
        },
    }


# ──────────────────────────────────────────────────────────
# 2. 루티 Phase 2 JSON 생성 (창고 → CY, 선적 재개 시)
# ──────────────────────────────────────────────────────────

def generate_phase2_routy_json(
    phase1_json: dict,
    cy_address: str,
    cy_closing_date: str,     # CY Cut — 출항 2~3일 전
) -> dict:
    """
    선적이 재개될 때 창고에서 CY로 운송하는 Phase 2 JSON을 생성합니다.
    Phase 1 JSON을 입력받아 자동으로 방향을 역전합니다.
    """
    now = datetime.now()
    p1 = phase1_json
    ship = p1["shipment"]
    dest = p1["dispatch"]["destination"]
    eg_id = p1["execution_group_id"].replace("STORAGE", "PHASE2")

    return {
        "execution_group_id": eg_id,
        "generated_at":       now.isoformat(timespec="seconds"),
        "phase":              "PHASE2_TO_CY",
        "phase_description":  "선적 재개 → 임시 창고에서 CY로 운송 (출항 준비)",

        "risk_context": {
            **p1["risk_context"],
            "phase2_triggered": now.strftime("%Y-%m-%d"),
            "cy_closing_date":  cy_closing_date,
        },

        "shipment": ship,

        "dispatch": {
            "origin": {
                "name":    dest["name"],
                "address": dest["address"],
                "phone":   dest["phone"],
            },
            "destination": {
                "name":    f"{p1['risk_context']['original_port']} CY",
                "address": cy_address,
            },
            "adjusted_pickup":   cy_closing_date,
            "action":            "DELIVER_TO_CY",
            "special_handling":  p1["dispatch"]["special_handling"],
        },

        "meta": {
            "note":               "위밋 플랫폼 → 루티 API 입력 스펙 (Phase 2: CY 반입)",
            "integration_status": "simulation_mode",
            "next_step_api":      "POST /v1/dispatch/execute",
            "phase1_ref":         p1["execution_group_id"],
        },
    }


# ──────────────────────────────────────────────────────────
# 3. JSON 파일 저장
# ──────────────────────────────────────────────────────────

def save_storage_json(data: dict, output_dir) -> "pathlib.Path":
    from pathlib import Path
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    fname = f"{data['execution_group_id']}.json"
    fpath = out_dir / fname
    fpath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return fpath
