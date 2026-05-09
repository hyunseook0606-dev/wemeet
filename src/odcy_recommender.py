"""
항만 주변 창고·ODCY 자동 탐색 및 추천 엔진
============================================
화주가 루티(ROOUTY)에 입력한 화물 정보(종류, 수량, 출발지, 도착지)를
활용하여 도착 항만 주변의 창고·ODCY를 탐색하고
3가지 방식(거리·시간·종합)으로 추천합니다.

운송 시나리오:
  1. 해상 리스크로 인해 선적이 지연될 가능성이 높아진 상황
  2. 화물이 아직 출발지(화주 공장/창고)에 있거나 루티 운송 중인 상황
  3. 플랫폼이 자동으로 항만 인근 보관 후보지를 찾아 화주에게 제시
  4. 화주가 선택한 후보지까지의 운송은 루티가 수행
  5. 선적 재개 시 해당 보관지에서 다시 CY로 루티 운송

API 연동:
  - 창고 검색: 카카오 Local API (Kakao Developers)
  - 경로/시간: 카카오모빌리티 길찾기 API
  - 보조 DB:   관세청 보세창고 정적 DB (CUSTOMS_WAREHOUSES) — 시뮬 모드
"""

from __future__ import annotations
import os
import math
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

# .env 자동 로드 (KAKAO_REST_API_KEY, KAKAO_MOBILITY_KEY)
try:
    from dotenv import load_dotenv
    from pathlib import Path
    _env_path = Path(__file__).parent.parent / '.env'
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# 1. 화물 종류 및 창고 요구사항 정의
# ──────────────────────────────────────────────────────────

class CargoType(str, Enum):
    """루티 입력 화물 유형 (ROOUTY 표준 항목 확장)"""
    GENERAL     = "일반화물"      # 잡화, 공산품
    REFRIGERATED = "냉장화물"     # 0~10°C (신선식품, 의약품)
    FROZEN      = "냉동화물"      # -25~-18°C (냉동식품)
    HAZMAT      = "위험물"        # IMDG 규정 해당
    AUTO_PARTS  = "자동차부품"    # 차량 부품, 중량기계
    BATTERY     = "2차전지"       # 리튬이온 배터리 (IMDG Class 9)
    APPAREL     = "의류/섬유"     # 의류, 원단
    ELECTRONICS = "전자제품"      # 반도체, 디스플레이


CARGO_REQUIREMENTS: dict[CargoType, dict] = {
    CargoType.GENERAL: {
        "description": "일반 잡화·공산품. 특수 조건 불필요.",
        "cold_chain": False,
        "hazmat": False,
        "required_keywords": ["물류창고", "물류센터", "CY", "보세창고"],  # 카카오 실검증
        "temp_range": None,
        "special_notes": "",
    },
    CargoType.REFRIGERATED: {
        "description": "0~10°C 유지 필요. 신선식품, 백신·의약품 등.",
        "cold_chain": True,
        "hazmat": False,
        "required_keywords": ["냉동창고", "냉장창고", "저온물류"],        # 카카오 실검증
        "temp_range": (0, 10),
        "special_notes": "냉장 시설 확인 필수",
    },
    CargoType.FROZEN: {
        "description": "-25~-18°C 유지 필요. 냉동식품·수산물.",
        "cold_chain": True,
        "hazmat": False,
        "required_keywords": ["냉동창고", "저온물류"],
        "temp_range": (-25, -18),
        "special_notes": "냉동 능력 및 전력 안정성 확인 필수",
    },
    CargoType.HAZMAT: {
        "description": "위험물 (IMDG 분류 1~9류). 허가된 보세창고 필수.",
        "cold_chain": False,
        "hazmat": True,
        "required_keywords": ["보세창고", "위험물창고"],                  # 카카오 실검증
        "temp_range": None,
        "special_notes": "관세청 위험물 보세창고 인허가 업체만 적합",
    },
    CargoType.AUTO_PARTS: {
        "description": "자동차 부품, 기계류. 중량물 랙·지게차 설비 필요.",
        "cold_chain": False,
        "hazmat": False,
        "required_keywords": ["물류창고", "물류센터", "CY"],
        "temp_range": None,
        "special_notes": "중량물 취급 장비 보유 여부 확인",
    },
    CargoType.BATTERY: {
        "description": "리튬이온 배터리 (IMDG Class 9). 온도+화재진압 필수.",
        "cold_chain": True,
        "hazmat": True,
        "required_keywords": ["보세창고", "위험물창고"],
        "temp_range": (15, 25),
        "special_notes": "화재진압 시스템(스프링클러) + 위험물 인허가 필수. IMDG Class 9 해당.",
    },
    CargoType.APPAREL: {
        "description": "의류·원단·섬유류. 방습·방진 조건 필요.",
        "cold_chain": False,
        "hazmat": False,
        "required_keywords": ["물류창고", "보세창고", "물류센터"],
        "temp_range": None,
        "special_notes": "습기·먼지 차단 환경 권장",
    },
    CargoType.ELECTRONICS: {
        "description": "전자제품·반도체·디스플레이. 정온·정전기 차단 필요.",
        "cold_chain": False,
        "hazmat": False,
        "required_keywords": ["보세창고", "물류센터", "물류창고"],
        "temp_range": (10, 30),
        "special_notes": "정전기 차폐(ESD) 환경 권장",
    },
}


# ──────────────────────────────────────────────────────────
# 2. 주요 항만 기준 좌표
# ──────────────────────────────────────────────────────────

PORT_COORDINATES: dict[str, tuple[float, float]] = {
    "부산항(북항)":   (35.1028, 129.0355),
    "부산 신항":      (35.0754, 128.7996),
    "인천항":         (37.4563, 126.5978),
    "평택항":         (36.9742, 126.8228),
    "광양항":         (34.9107, 127.7018),
    "울산항":         (35.5060, 129.3874),
}


# ──────────────────────────────────────────────────────────
# 3. 시뮬레이션용 정적 창고 DB (API 없이도 동작)
#    출처: 부산항만공사 ODCY 목록, 관세청 보세창고 인허가 정보 기반
# ──────────────────────────────────────────────────────────

SIMULATION_WAREHOUSES: list[dict] = [
    # ── 부산 북항 권역 ──────────────────────────────────
    {
        "id": "W001", "name": "선광 ODCY (북항)",
        "lat": 35.1085, "lng": 129.0435,
        "address": "부산광역시 동구 초량동",
        "phone": "051-441-XXXX",
        "type": "ODCY",
        "facility_tags": ["일반화물", "컨테이너야드"],
        "cargo_types": [CargoType.GENERAL, CargoType.AUTO_PARTS, CargoType.APPAREL],
        "area_sqm": 28000,
        "bonded": True,
        "hazmat_license": False,
        "cold_chain": False,
        "operating_hours": "24시간",
    },
    {
        "id": "W002", "name": "CJ대한통운 부산 물류센터 (북항)",
        "lat": 35.1010, "lng": 129.0480,
        "address": "부산광역시 동구 범일동",
        "phone": "051-XXX-XXXX",
        "type": "물류창고",
        "facility_tags": ["일반창고", "냉장", "보세"],
        "cargo_types": [CargoType.GENERAL, CargoType.REFRIGERATED, CargoType.APPAREL, CargoType.ELECTRONICS],
        "area_sqm": 15000,
        "bonded": True,
        "hazmat_license": False,
        "cold_chain": True,
        "cold_temp_range": (0, 10),
        "operating_hours": "06:00~22:00",
    },
    {
        "id": "W003", "name": "부산항 위험물 보세창고",
        "lat": 35.0985, "lng": 129.0510,
        "address": "부산광역시 중구 중앙동",
        "phone": "051-XXX-XXXX",
        "type": "보세창고(위험물)",
        "facility_tags": ["위험물 허가", "보세창고", "IMDG"],
        "cargo_types": [CargoType.HAZMAT, CargoType.BATTERY],
        "area_sqm": 5000,
        "bonded": True,
        "hazmat_license": True,
        "cold_chain": False,
        "operating_hours": "09:00~18:00",
    },
    # ── 부산 신항 권역 ──────────────────────────────────
    {
        "id": "W004", "name": "한진 부산 신항 ODCY",
        "lat": 35.0750, "lng": 128.7985,
        "address": "경상남도 창원시 진해구 용원동",
        "phone": "055-XXX-XXXX",
        "type": "ODCY",
        "facility_tags": ["컨테이너야드", "일반화물"],
        "cargo_types": [CargoType.GENERAL, CargoType.AUTO_PARTS],
        "area_sqm": 42000,
        "bonded": True,
        "hazmat_license": False,
        "cold_chain": False,
        "operating_hours": "24시간",
    },
    {
        "id": "W005", "name": "현대글로비스 부산 신항 물류센터",
        "lat": 35.0780, "lng": 128.8020,
        "address": "경상남도 창원시 진해구 명동",
        "phone": "055-XXX-XXXX",
        "type": "물류창고",
        "facility_tags": ["자동차부품", "중량물", "일반창고"],
        "cargo_types": [CargoType.AUTO_PARTS, CargoType.GENERAL],
        "area_sqm": 35000,
        "bonded": True,
        "hazmat_license": False,
        "cold_chain": False,
        "operating_hours": "24시간",
    },
    {
        "id": "W006", "name": "신항 냉동·냉장 물류센터 (STX)",
        "lat": 35.0730, "lng": 128.8050,
        "address": "경상남도 창원시 진해구 용원동",
        "phone": "055-XXX-XXXX",
        "type": "냉동·냉장창고",
        "facility_tags": ["냉동창고", "냉장창고", "저온물류"],
        "cargo_types": [CargoType.FROZEN, CargoType.REFRIGERATED],
        "area_sqm": 12000,
        "bonded": True,
        "hazmat_license": False,
        "cold_chain": True,
        "cold_temp_range": (-25, 10),
        "operating_hours": "24시간",
    },
    {
        "id": "W007", "name": "신항 배터리·위험물 전용창고",
        "lat": 35.0760, "lng": 128.7960,
        "address": "경상남도 창원시 진해구 용원동",
        "phone": "055-XXX-XXXX",
        "type": "위험물창고",
        "facility_tags": ["2차전지", "위험물 허가", "화재진압", "온도제어"],
        "cargo_types": [CargoType.BATTERY, CargoType.HAZMAT],
        "area_sqm": 8000,
        "bonded": True,
        "hazmat_license": True,
        "cold_chain": True,
        "cold_temp_range": (15, 25),
        "operating_hours": "24시간",
    },
    # ── 감천·다대포 권역 ────────────────────────────────
    {
        "id": "W008", "name": "감천항 ODCY",
        "lat": 35.0712, "lng": 128.9628,
        "address": "부산광역시 사하구 감천동",
        "phone": "051-XXX-XXXX",
        "type": "ODCY",
        "facility_tags": ["컨테이너야드", "일반화물"],
        "cargo_types": [CargoType.GENERAL, CargoType.APPAREL],
        "area_sqm": 20000,
        "bonded": True,
        "hazmat_license": False,
        "cold_chain": False,
        "operating_hours": "06:00~22:00",
    },
    {
        "id": "W009", "name": "다대포 전자제품 보관창고",
        "lat": 35.0580, "lng": 128.9620,
        "address": "부산광역시 사하구 다대동",
        "phone": "051-XXX-XXXX",
        "type": "보세창고",
        "facility_tags": ["정온창고", "전자제품", "보세"],
        "cargo_types": [CargoType.ELECTRONICS, CargoType.GENERAL],
        "area_sqm": 9000,
        "bonded": True,
        "hazmat_license": False,
        "cold_chain": False,
        "operating_hours": "09:00~18:00",
    },
]


# ──────────────────────────────────────────────────────────
# 4. 거리 계산 유틸리티 (Haversine)
# ──────────────────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 직선 거리를 킬로미터로 반환 (Haversine 공식)"""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────
# 5. 카카오 API 연동 (실제 모드)
# ──────────────────────────────────────────────────────────

def search_kakao_local(
    keyword: str,
    lat: float,
    lng: float,
    radius_m: int = 15000,
    kakao_rest_key: Optional[str] = None,
) -> list[dict]:
    """
    카카오 Local Keyword Search API로 항만 주변 창고·ODCY 검색.

    Parameters
    ----------
    keyword    : 검색어 (예: "물류창고", "보세창고", "ODCY")
    lat / lng  : 검색 중심 좌표 (항만 기준)
    radius_m   : 검색 반경 (미터, 최대 20,000)
    kakao_rest_key : 카카오 REST API 키 (.env의 KAKAO_REST_API_KEY)

    Returns
    -------
    list[dict] : 검색 결과 창고 목록 (raw Kakao API 응답)
    """
    if not _REQUESTS_OK:
        logger.warning("requests 미설치 → 시뮬레이션 모드로 전환")
        return []

    key = kakao_rest_key or os.getenv("KAKAO_REST_API_KEY", "")
    if not key:
        logger.warning("KAKAO_REST_API_KEY 없음 → 시뮬레이션 모드로 전환")
        return []

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {key}"}
    params = {
        "query": keyword,
        "x": lng,
        "y": lat,
        "radius": radius_m,
        "size": 15,
        "sort": "distance",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        resp.raise_for_status()
        return resp.json().get("documents", [])
    except Exception as e:
        logger.error(f"카카오 Local API 오류: {e}")
        return []


def get_kakao_route(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    kakao_mobility_key: Optional[str] = None,
) -> dict:
    """
    카카오모빌리티 길찾기 API로 두 지점 간 거리·소요 시간 조회.

    Returns
    -------
    dict : {"distance_m": int, "duration_sec": int, "distance_km": float,
            "duration_min": float, "source": "kakao" | "haversine"}
    """
    if not _REQUESTS_OK:
        return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)

    key = kakao_mobility_key or os.getenv("KAKAO_MOBILITY_KEY", "")
    if not key:
        return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)

    url = "https://apis-navi.kakaomobility.com/v1/directions"
    headers = {"Authorization": f"KakaoAK {key}"}
    params = {
        "origin":      f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
        "priority":    "DISTANCE",
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)
        route_obj = routes[0]
        # result_code 0 = 성공, 그 외는 경로 없음
        if route_obj.get("result_code", -1) != 0:
            return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)
        summary = route_obj.get("summary", {})
        dist_m  = summary.get("distance", 0)
        dur_s   = summary.get("duration", 0)
        if dist_m == 0:
            return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)
        return {
            "distance_m":   dist_m,
            "duration_sec": dur_s,
            "distance_km":  round(dist_m / 1000, 2),
            "duration_min": round(dur_s / 60, 1),
            "source": "kakao",
        }
    except Exception as e:
        logger.debug(f"카카오모빌리티 폴백: {e}")
        return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)


def _fallback_route(
    lat1: float, lng1: float, lat2: float, lng2: float,
) -> dict:
    """API 없을 때 Haversine 직선거리 기반 소요시간 추정 (평균 속도 40 km/h 가정)"""
    km = haversine_km(lat1, lng1, lat2, lng2)
    dur_min = (km / 40) * 60
    return {
        "distance_m":   int(km * 1000),
        "duration_sec": int(dur_min * 60),
        "distance_km":  round(km, 2),
        "duration_min": round(dur_min, 1),
        "source": "haversine_estimate",
    }


# ──────────────────────────────────────────────────────────
# 6. 창고 적합성 필터
# ──────────────────────────────────────────────────────────

def filter_by_cargo_type(
    warehouses: list[dict],
    cargo_type: CargoType,
) -> list[dict]:
    """
    화물 종류 요구사항에 맞는 창고만 필터링합니다.
    시뮬레이션 DB에서는 cargo_types 필드,
    카카오 API 결과에서는 place_name 키워드로 판단합니다.
    """
    reqs = CARGO_REQUIREMENTS[cargo_type]
    filtered = []
    for wh in warehouses:
        # ── 시뮬레이션 DB 창고 ──
        if "cargo_types" in wh:
            if cargo_type in wh["cargo_types"]:
                filtered.append(wh)
            continue

        # ── 카카오 API 결과 창고 (place_name 기반 판단) ──
        name = wh.get("place_name", "").lower()
        keywords = [k.lower() for k in reqs["required_keywords"]]
        if any(kw in name for kw in keywords):
            # cold_chain 필수인 경우 냉장/냉동 키워드 체크
            if reqs["cold_chain"] and not any(
                kw in name for kw in ["냉장", "냉동", "저온", "콜드"]
            ):
                continue
            if reqs["hazmat"] and not any(
                kw in name for kw in ["위험물", "hazmat", "배터리"]
            ):
                continue
            filtered.append(wh)

    return filtered


# ──────────────────────────────────────────────────────────
# 7. 3가지 추천 모드
# ──────────────────────────────────────────────────────────

def score_warehouses(
    warehouses: list[dict],
    port_lat: float,
    port_lng: float,
    mode: str = "comprehensive",
) -> list[dict]:
    """
    각 창고에 경로 정보를 붙이고 mode에 따라 점수를 매겨 정렬합니다.

    mode:
      "distance"     — 항만에서 가장 가까운 순
      "time"         — 이동 시간이 가장 짧은 순
      "comprehensive"— 거리·시간·시설 완성도를 종합 고려
    """
    for wh in warehouses:
        wh_lat = wh.get("lat") or float(wh.get("y", 0))
        wh_lng = wh.get("lng") or float(wh.get("x", 0))
        route  = get_kakao_route(port_lat, port_lng, wh_lat, wh_lng)
        wh["route"] = route
        wh["distance_km"]  = route["distance_km"]
        wh["duration_min"] = route["duration_min"]

    if not warehouses:
        return []

    max_dist = max(w["distance_km"] for w in warehouses) or 1
    max_dur  = max(w["duration_min"] for w in warehouses) or 1

    for wh in warehouses:
        dist_norm = wh["distance_km"] / max_dist   # 낮을수록 좋음
        time_norm = wh["duration_min"] / max_dur   # 낮을수록 좋음

        # 시설 완성도 점수 (bonded, hazmat_license, cold_chain 보유 가중)
        facility_score = (
            0.1 * int(wh.get("bonded", False))
            + 0.1 * int(wh.get("hazmat_license", False))
            + 0.1 * int(wh.get("cold_chain", False))
        )

        if mode == "distance":
            wh["score"] = dist_norm
        elif mode == "time":
            wh["score"] = time_norm
        else:  # comprehensive
            wh["score"] = 0.4 * dist_norm + 0.4 * time_norm - facility_score

    warehouses.sort(key=lambda w: w["score"])
    return warehouses


# ──────────────────────────────────────────────────────────
# 8. 메인 추천 함수
# ──────────────────────────────────────────────────────────

def recommend_storage(
    port_name: str,
    cargo_type: CargoType,
    top_n: int = 3,
    search_radius_m: int = 15000,
    kakao_rest_key: Optional[str] = None,
    kakao_mobility_key: Optional[str] = None,
) -> dict:
    """
    도착 항만 기준으로 화물 유형에 맞는 창고·ODCY 후보를 탐색하고
    3가지 모드별 추천 결과를 반환합니다.

    Parameters
    ----------
    port_name        : 도착 항만 이름 (PORT_COORDINATES 키)
    cargo_type       : 화물 유형 (CargoType enum)
    top_n            : 각 모드별 추천 개수
    search_radius_m  : 카카오 API 검색 반경 (미터)
    kakao_rest_key   : 카카오 REST API 키 (없으면 시뮬레이션 모드)
    kakao_mobility_key : 카카오모빌리티 API 키

    Returns
    -------
    dict : {
        "port": str,
        "cargo_type": str,
        "cargo_requirements": dict,
        "recommendations": {
            "distance": list[dict],
            "time":     list[dict],
            "comprehensive": list[dict],
        },
        "simulation_mode": bool,
    }
    """
    port_coords = PORT_COORDINATES.get(port_name)
    if port_coords is None:
        raise ValueError(f"알 수 없는 항만: {port_name}. 사용 가능: {list(PORT_COORDINATES.keys())}")

    port_lat, port_lng = port_coords
    reqs = CARGO_REQUIREMENTS[cargo_type]

    # ── 창고 탐색 ───────────────────────────────────────────
    # 1) 카카오 API (실제 모드)
    kakao_results: list[dict] = []
    simulation_mode = True

    if kakao_rest_key or os.getenv("KAKAO_REST_API_KEY"):
        for keyword in reqs["required_keywords"]:
            results = search_kakao_local(
                keyword, port_lat, port_lng, search_radius_m,
                kakao_rest_key=kakao_rest_key,
            )
            kakao_results.extend(results)
        if kakao_results:
            simulation_mode = False

    # 2) 시뮬레이션 DB (API 없을 때 또는 보완)
    sim_results = [
        wh for wh in SIMULATION_WAREHOUSES
        if haversine_km(port_lat, port_lng, wh["lat"], wh["lng"]) * 1000 <= search_radius_m
    ]

    raw_pool = (kakao_results + sim_results) if not simulation_mode else sim_results

    # ── 화물 유형 필터 ──────────────────────────────────────
    filtered = filter_by_cargo_type(raw_pool, cargo_type)
    if not filtered:
        # 필터가 너무 좁으면 전체로 fallback
        filtered = raw_pool

    # ── 3가지 모드별 점수 산정 ──────────────────────────────
    import copy
    dist_ranked  = score_warehouses(copy.deepcopy(filtered), port_lat, port_lng, "distance")[:top_n]
    time_ranked  = score_warehouses(copy.deepcopy(filtered), port_lat, port_lng, "time")[:top_n]
    comp_ranked  = score_warehouses(copy.deepcopy(filtered), port_lat, port_lng, "comprehensive")[:top_n]

    def _clean(wh_list: list[dict]) -> list[dict]:
        out = []
        for w in wh_list:
            entry = {
                "id":           w.get("id") or w.get("id", ""),
                "name":         w.get("name") or w.get("place_name", ""),
                "address":      w.get("address") or w.get("address_name", ""),
                "phone":        w.get("phone") or w.get("phone", ""),
                "type":         w.get("type", "창고"),
                "bonded":       w.get("bonded", None),
                "hazmat_license": w.get("hazmat_license", None),
                "cold_chain":   w.get("cold_chain", None),
                "area_sqm":     w.get("area_sqm", None),
                "distance_km":  w.get("distance_km"),
                "duration_min": w.get("duration_min"),
                "route_source": w.get("route", {}).get("source", ""),
                "operating_hours": w.get("operating_hours", ""),
                "special_notes": reqs["special_notes"],
            }
            out.append(entry)
        return out

    return {
        "port":              port_name,
        "port_coords":       {"lat": port_lat, "lng": port_lng},
        "cargo_type":        cargo_type.value,
        "cargo_requirements": {
            "description":  reqs["description"],
            "cold_chain":   reqs["cold_chain"],
            "hazmat":       reqs["hazmat"],
            "temp_range":   reqs["temp_range"],
            "special_notes": reqs["special_notes"],
        },
        "recommendations": {
            "distance":      _clean(dist_ranked),
            "time":          _clean(time_ranked),
            "comprehensive": _clean(comp_ranked),
        },
        "simulation_mode":   simulation_mode,
    }


# ──────────────────────────────────────────────────────────
# 9. 고객 메시지 포매터
# ──────────────────────────────────────────────────────────

def format_storage_message(result: dict) -> str:
    """
    추천 결과를 고객이 읽기 쉬운 한국어 형식으로 변환합니다.
    홈페이지 팝업 또는 앱 알림에 사용.
    """
    lines = [
        f"📦 화물 유형: {result['cargo_type']}",
        f"🚢 도착 항만: {result['port']}",
        f"⚠️  {result['cargo_requirements']['special_notes']}" if result['cargo_requirements']['special_notes'] else "",
        "",
        "━━━ 추천 창고·ODCY ━━━",
        "",
    ]

    mode_labels = {
        "distance":      "📍 거리 최단 추천",
        "time":          "⏱  이동시간 최단 추천",
        "comprehensive": "⭐ 종합 추천 (거리+시간+시설)",
    }

    for mode_key, label in mode_labels.items():
        items = result["recommendations"][mode_key]
        lines.append(f"── {label} ──")
        for i, wh in enumerate(items, 1):
            lines.append(f"  {i}. {wh['name']}")
            lines.append(f"     주소: {wh['address']}")
            lines.append(f"     전화: {wh['phone']}")
            lines.append(f"     거리: {wh['distance_km']} km  |  소요: {wh['duration_min']} 분")
            if wh.get("area_sqm"):
                lines.append(f"     면적: {wh['area_sqm']:,} ㎡")
            if wh.get("operating_hours"):
                lines.append(f"     운영: {wh['operating_hours']}")
            if mode_key == "comprehensive" and i == 1:
                lines.append("     ★ 루티(ROOUTY) 운송 추천 대상")
        lines.append("")

    sim_note = "⚡ 시뮬레이션 모드: 카카오 API 키 설정 시 실시간 검색으로 전환됩니다."
    if result["simulation_mode"]:
        lines.append(sim_note)

    return "\n".join(l for l in lines if l is not None)


def to_json(result: dict) -> str:
    """API 응답용 JSON 직렬화"""
    def _default(obj):
        if isinstance(obj, CargoType):
            return obj.value
        raise TypeError(f"직렬화 불가 타입: {type(obj)}")
    return json.dumps(result, ensure_ascii=False, indent=2, default=_default)
