"""
api.py — 위밋모빌리티 플랫폼 FastAPI 백엔드
실행: uvicorn api:app --reload --port 8000

Lovable 프론트엔드가 호출하는 REST API 엔드포인트 모음.
CORS 허용 설정 포함 (Lovable 도메인에서 호출 가능).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

import numpy as np
import pandas as pd

from src.config import SCENARIOS, ROUTE_INFO
from src.nlp_classifier import classify_news_df, top_category
from src.mri_engine import calc_today_mri, build_mri_series, mri_grade, mri_sub_indices
from src.scenario_engine import auto_classify_scenario, analyze_impact, ImpactAnalysis
from src.historical_matcher import find_similar_events
from src.odcy_recommender import recommend_storage, CargoType
from src.option_presenter import generate_four_options
from src.storage_routy_adapter import (
    generate_storage_routy_json, generate_phase2_routy_json,
)
from src.data_loader import load_kcci

app = FastAPI(
    title='위밋모빌리티 해상 리스크 플랫폼 API',
    version='1.0.0',
    description='Lovable 프론트엔드 연동용 REST API',
)

# ── CORS — Lovable 프리뷰 도메인 허용 ──────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],   # 배포 시 Lovable 실제 도메인으로 제한 권장
    allow_methods=['*'],
    allow_headers=['*'],
)

# ── 캐시 (프로세스 내 1회) ─────────────────────────────────────────────────
_NEWS_CACHE: pd.DataFrame | None = None
_MRI_CACHE:  dict | None         = None


def _get_mri_data() -> dict:
    """MRI 계산 결과 캐시 (1시간 TTL 생략 — 단순화)."""
    global _NEWS_CACHE, _MRI_CACHE
    if _MRI_CACHE is not None:
        return _MRI_CACHE

    try:
        from src.real_data_fetcher import fetch_maritime_news
        import feedparser  # noqa
        news_df = fetch_maritime_news(max_per_source=10, days_back=7)
    except Exception:
        news_df = pd.DataFrame([
            {'title': 'Houthi attack Red Sea blockade', 'text': 'hormuz threat iran', 'source': 'sim'},
            {'title': '호르무즈 봉쇄 위협', 'text': '이란 미사일 위협', 'source': 'sim'},
            {'title': 'freight rate surge SCFI', 'text': 'capacity shortage bunker', 'source': 'sim'},
        ])

    news_df = classify_news_df(news_df)
    freight_df = load_kcci(ROOT / 'data', use_real=True)

    today = calc_today_mri(news_df, freight_df)
    grade, color = mri_grade(today)
    cat = top_category(news_df)
    sub = mri_sub_indices(news_df, freight_df)

    _NEWS_CACHE = news_df
    _MRI_CACHE  = {
        'mri': round(today, 4),
        'grade': grade,
        'color': color,
        'category': cat,
        'sub_indices': {k: round(v, 4) for k, v in sub.items()},
    }
    return _MRI_CACHE


# ══════════════════════════════════════════════════════════════════
# Schema (Pydantic 요청/응답 모델)
# ══════════════════════════════════════════════════════════════════

class ShipmentRequest(BaseModel):
    company:       str   = Field(..., example='(주)경기식품')
    cargo_type:    str   = Field(..., example='일반화물')   # 일반화물/냉장화물/위험물
    cbm:           float = Field(..., example=15.0)
    route:         str   = Field(..., example='부산→로테르담')
    pickup_date:   str   = Field(..., example='2026-05-20')
    deadline_days: int   = Field(..., example=14)
    region:        str   = Field('경기남부', example='경기남부')
    urgent:        bool  = Field(False)


class WarehouseRequest(BaseModel):
    port_name:  str   = Field('부산항(북항)', example='부산항(북항)')
    cargo_type: str   = Field('일반화물')
    cbm:        float = Field(15.0)
    mri_score:  float = Field(0.7)
    delay_days: int   = Field(14)
    freight_usd: int  = Field(675)


class RoutyJsonRequest(BaseModel):
    shipment_id:       str
    company:           str
    region:            str
    cargo_type:        str
    cbm:               float
    origin_address:    str
    port_name:         str
    pickup_date:       str
    mri_current:       float
    delay_reason:      str
    warehouse_name:    str
    warehouse_address: str
    warehouse_km:      float
    warehouse_minutes: float
    warehouse_hours:   str = ''
    phase2_ready_date: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# 엔드포인트
# ══════════════════════════════════════════════════════════════════

@app.get('/api/health')
def health():
    """서버 상태 확인."""
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}


# ── Step 2: MRI 현황 + 과거 유사사례 + LSTM ───────────────────────

@app.get('/api/mri')
def get_mri():
    """
    현재 MRI 점수·등급·카테고리·하위지수 반환.
    뉴스 RSS 자동 수집 (feedparser 없으면 시뮬 데이터).
    """
    data = _get_mri_data()
    scenario_id = auto_classify_scenario(data['mri'], data['category'])
    scenario    = SCENARIOS[scenario_id]
    return {
        **data,
        'scenario_id':   scenario_id,
        'scenario_name': scenario['name'],
        'scenario_icon': scenario['icon'],
        'delay_days':    scenario['delay_days'],
        'freight_surge': scenario['freight_surge_pct'],
    }


@app.get('/api/mri/similar-events')
def get_similar_events(top_k: int = 3):
    """현재 MRI와 유사했던 과거 사례 반환 (평균 지연·운임 포함)."""
    data = _get_mri_data()
    cats = [data['category']] if data['category'] != '정상' else ['지정학분쟁']
    events = find_similar_events(data['mri'], cats, top_k=top_k)
    if not events:
        return {'events': [], 'avg_delay': 0, 'avg_freight': 0}
    avg_delay   = sum(e['avg_delay_days']           for e in events) / len(events)
    avg_freight = sum(e['avg_freight_increase_pct'] for e in events) / len(events)
    return {
        'events':      events,
        'avg_delay':   round(avg_delay, 1),
        'avg_freight': round(avg_freight, 1),
    }


@app.get('/api/mri/lstm-forecast')
def get_lstm_forecast():
    """LSTM 부산항 물동량 3개월 예측.
    우선순위: ① 사전계산 캐시(data/lstm_cache.json) → ② 실시간 학습(torch 있을 때) → ③ 시뮬값
    """
    import json as _json

    # ① 캐시 파일 우선 (서버 배포 환경 — torch 불필요)
    cache_path = ROOT / 'data' / 'lstm_cache.json'
    if cache_path.exists():
        try:
            with open(cache_path, encoding='utf-8') as f:
                cached = _json.load(f)
            return {
                'forecast': cached['forecast'],
                'mape': cached['mape'],
                'source': 'lstm_cached',
                'generated_at': cached.get('generated_at', ''),
            }
        except Exception:
            pass  # 캐시 손상 시 아래로 계속

    # ② 실시간 학습 (로컬 환경 — torch 설치된 경우)
    try:
        from src.lstm_forecaster import build_main_df, train_and_forecast, HORIZON
        from src.mri_engine import build_mri_series
        dates  = pd.date_range('2020-01-01', '2026-04-01', freq='MS')
        mri_s  = build_mri_series(dates)
        mdf    = build_main_df(dates, mri_s)
        result = train_and_forecast(mdf, epochs=60)
        labels = pd.date_range('2026-04-01', periods=HORIZON, freq='MS')
        return {
            'forecast': [
                {'month': l.strftime('%Y.%m'), 'teu_10k': round(float(v), 2)}
                for l, v in zip(labels, result['future_real'])
            ],
            'mape': round(result['mape_3m'], 2),
            'source': 'lstm',
        }
    except Exception:
        pass

    # ③ 폴백 시뮬 (캐시도 없고 torch도 없을 때)
    return {
        'forecast': [
            {'month': '2026.04', 'teu_10k': 198.5},
            {'month': '2026.05', 'teu_10k': 195.2},
            {'month': '2026.06', 'teu_10k': 193.8},
        ],
        'mape': -1,
        'source': 'simulation',
    }


# ── Step 1 + Step 2: 화주 출하 등록 + 영향 분석 ──────────────────

@app.post('/api/shipment/register')
def register_shipment(req: ShipmentRequest):
    """
    화주 출하 등록 → 현재 시나리오 기반 영향 분석 반환.
    """
    mri_data    = _get_mri_data()
    scenario_id = auto_classify_scenario(mri_data['mri'], mri_data['category'])
    scenario    = SCENARIOS[scenario_id]

    if req.route not in ROUTE_INFO:
        raise HTTPException(400, f'알 수 없는 항로: {req.route}')

    info     = ROUTE_INFO[req.route]
    est_cost = round((info['usd_per_teu'] / 33) * 1.5 * req.cbm)

    ship = {
        'shipment_id':   f'SH-{datetime.now().strftime("%H%M%S")}',
        'company':       req.company,
        'route':         req.route,
        'cargo_type':    req.cargo_type,
        'region':        req.region,
        'pickup_date':   datetime.strptime(req.pickup_date, '%Y-%m-%d'),
        'cbm':           req.cbm,
        'deadline_days': req.deadline_days,
        'urgent':        req.urgent,
        'estimated_cost': est_cost,
    }

    ia: ImpactAnalysis = analyze_impact(ship, scenario)

    # 항로 → 출발 항만
    route_to_port = {
        '부산→로테르담': '부산항(북항)',
        '부산→LA':       '부산항(북항)',
        '부산→상하이':   '부산항(북항)',
        '부산→싱가포르': '부산 신항',
        '부산→도쿄':     '부산항(북항)',
    }
    return {
        'shipment_id':      ship['shipment_id'],
        'estimated_cost':   est_cost,
        'delay_days':       ia.delay_days_applied,
        'cost_delta':       ia.cost_delta,
        'deadline_violated': ia.deadline_violated,
        'requires_priority': ia.requires_priority,
        'requires_holdback': ia.requires_holdback,
        'reason':            ia.reason,
        'new_pickup_date':   ia.new_pickup_date.strftime('%Y-%m-%d'),
        'scenario_id':       scenario_id,
        'mri':               mri_data['mri'],
        'departure_port':    route_to_port.get(req.route, '부산항(북항)'),
        'show_warehouse':    mri_data['mri'] >= 0.5,   # 창고 추천 활성화 여부
    }


# ── Step 3: 창고·ODCY 추천 + 4가지 옵션 ─────────────────────────

@app.post('/api/warehouse/recommend')
def warehouse_recommend(req: WarehouseRequest):
    """
    항만 주변 창고·ODCY 탐색 + A/B/C/D 4가지 옵션 비용 비교.
    카카오 API 키 있으면 실데이터, 없으면 시뮬 DB.
    """
    cargo_map = {
        '일반화물': CargoType.GENERAL,
        '냉장화물': CargoType.REFRIGERATED,
        '위험물':   CargoType.HAZMAT,
        '자동차부품': CargoType.AUTO_PARTS,
        '2차전지':  CargoType.BATTERY,
        '의류/섬유': CargoType.APPAREL,
        '전자제품': CargoType.ELECTRONICS,
    }
    cargo_enum = cargo_map.get(req.cargo_type, CargoType.GENERAL)
    kakao_key  = os.getenv('KAKAO_REST_API_KEY', '')
    mobi_key   = os.getenv('KAKAO_MOBILITY_KEY', '')

    storage = recommend_storage(
        port_name=req.port_name,
        cargo_type=cargo_enum,
        top_n=3,
        kakao_rest_key=kakao_key or None,
        kakao_mobility_key=mobi_key or None,
    )

    shipment_dict = {
        'cargo_type': req.cargo_type,
        'cbm':        req.cbm,
        'region':     '경기남부',
    }
    options = generate_four_options(
        shipment=shipment_dict,
        storage_result=storage,
        delay_days=req.delay_days,
        freight_usd=req.freight_usd,
    )

    warehouses = []
    for w in storage['recommendations']['comprehensive']:
        warehouses.append({
            'name':            w.get('name', ''),
            'address':         w.get('address', ''),
            'distance_km':     w.get('distance_km'),
            'duration_min':    w.get('duration_min'),
            'operating_hours': w.get('operating_hours', ''),
            'bonded':          w.get('bonded'),
            'cold_chain':      w.get('cold_chain'),
            'special_notes':   w.get('special_notes', ''),
            'route_source':    w.get('route_source', ''),
        })

    return {
        'simulation_mode': storage['simulation_mode'],
        'warehouses':      warehouses,
        'options': [
            {
                'id':          o.option_id,
                'name':        o.option_name,
                'description': o.description,
                'total_usd':   round(o.total_usd, 0),
                'savings_usd': round(o.savings_vs(options[0]), 0) if i > 0 else 0,
                'savings_pct': round(o.savings_pct_vs(options[0]), 1) if i > 0 else 0,
                'breakdown': {
                    'freight':   round(o.freight_usd, 0),
                    'routy_p1':  round(o.routy_phase1_usd, 0),
                    'routy_p2':  round(o.routy_phase2_usd, 0),
                    'rental':    round(o.warehouse_rental_usd, 0),
                    'contract':  round(o.warehouse_contract_usd, 0),
                    'risk':      round(o.risk_penalty_usd, 0),
                },
                'recommended': o.option_id == 'D',
                'warehouse_name': o.warehouse.get('name', '') if o.warehouse else '',
            }
            for i, o in enumerate(options)
        ],
    }


# ── Step 4: 루티 JSON 생성 ────────────────────────────────────────

@app.post('/api/routy/generate')
def generate_routy(req: RoutyJsonRequest):
    """Phase 1 + Phase 2 루티 JSON 생성 및 반환."""
    wh = {
        'name':             req.warehouse_name,
        'address':          req.warehouse_address,
        'phone':            '',
        'type':             '창고',
        'distance_km':      req.warehouse_km,
        'duration_min':     req.warehouse_minutes,
        'special_notes':    '',
        'operating_hours':  req.warehouse_hours,
    }
    cold   = req.cargo_type in ('냉장화물', '냉동화물', '2차전지')
    hazmat = req.cargo_type in ('위험물', '2차전지')

    phase1 = generate_storage_routy_json(
        shipment_id=req.shipment_id,
        company=req.company, region=req.region,
        cargo_type=req.cargo_type, cbm=req.cbm,
        cold_chain=cold, hazmat=hazmat,
        origin_address=req.origin_address,
        original_port=req.port_name,
        original_pickup_date=req.pickup_date,
        mri_current=req.mri_current,
        delay_reason=req.delay_reason,
        recommended_warehouse=wh,
        phase2_ready_date=req.phase2_ready_date,
    )
    phase2 = generate_phase2_routy_json(
        phase1_json=phase1,
        cy_address=f'{req.port_name} CY',
        cy_closing_date=req.phase2_ready_date or '2026-06-05',
    )
    return {'phase1': phase1, 'phase2': phase2}


# ── 항로 목록 ─────────────────────────────────────────────────────

@app.get('/api/routes')
def get_routes():
    """이용 가능한 항로 목록 반환."""
    return {
        'routes': [
            {
                'id':           route,
                'name':         route,
                'transit_days': info['transit_days'],
                'usd_per_teu':  info['usd_per_teu'],
            }
            for route, info in ROUTE_INFO.items()
        ]
    }
