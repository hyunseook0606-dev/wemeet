"""
api.py — 위밋모빌리티 플랫폼 FastAPI 백엔드
실행: uvicorn api:app --reload --port 8000

React 프론트엔드가 호출하는 REST API 엔드포인트 모음.
CORS 허용 설정 포함.
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

from src.config import ROUTE_INFO, RISK_KEYWORDS
from src.nlp_classifier import classify_news_df, top_category
from src.mri_engine import calc_today_mri, build_mri_series, mri_grade, mri_sub_indices
from src.scenario_engine import (
    build_risk_context, estimate_impact_advisory,
)
from src.historical_matcher import find_similar_events
from src.odcy_recommender import recommend_nearest_five, calc_total_with_user_price, CargoType, PORT_COORDINATES
from src.scenario_cost import calc_scenarios, scenario_to_dict
from src.storage_routy_adapter import generate_storage_routy_json
from src.data_loader import load_kcci

app = FastAPI(
    title='위밋모빌리티 해상 리스크 플랫폼 API',
    version='1.0.0',
    description='위밋모빌리티 × KMI 해상 리스크 플랫폼 REST API',
)

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# ── 캐시 (프로세스 내 1회) ─────────────────────────────────────────────────
_NEWS_CACHE: pd.DataFrame | None = None
_MRI_CACHE:  dict | None         = None

_GEO_SIGNALS = {
    'iran', 'hormuz', '이란', '호르무즈', 'houthi', '후티',
    'blockade', '봉쇄', 'red sea', '홍해', 'war', 'conflict',
    'attack', 'seizure', 'strait', 'suez', '수에즈',
}


def _effective_category(category: str, news_kws: list[str], sub: dict) -> str:
    """top_category='정상'이지만 키워드/sub_indices에 실제 리스크 신호가 있으면 보정."""
    if category != '정상':
        return category
    kw_lower = {k.lower() for k in news_kws}
    if kw_lower & _GEO_SIGNALS or sub.get('G', 0) > 0.4:
        return '지정학분쟁'
    if sub.get('P', 0) > 0.4:
        return '관세정책'
    if sub.get('F', 0) > 0.4:
        return '운임급등'
    return category


def _get_mri_data() -> dict:
    """MRI 계산 결과 캐시 (프로세스 내 1회)."""
    global _NEWS_CACHE, _MRI_CACHE
    if _MRI_CACHE is not None:
        return _MRI_CACHE

    data_source = 'simulation'
    news_count  = 0

    try:
        from src.real_data_fetcher import fetch_maritime_news
        import feedparser  # noqa
        news_df = fetch_maritime_news(max_per_source=30, days_back=30)
        # 시뮬 소스가 아닌 실제 뉴스 기사 수 확인
        real_count = int((news_df.get('source', pd.Series(dtype=str)) != 'sim').sum())
        if real_count > 0:
            data_source = 'realtime'
            news_count  = real_count
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

    # 뉴스 타이틀에서 상위 키워드 추출 (top_category 우선, 나머지 보충)
    extracted_kws: list[str] = []
    if not news_df.empty and 'title' in news_df.columns:
        all_titles = ' '.join(news_df['title'].fillna('').tolist()).lower()
        check_order = [cat] + [c for c in RISK_KEYWORDS if c != cat]
        for check_cat in check_order:
            for kw in RISK_KEYWORDS.get(check_cat, []):
                if len(kw) >= 2 and kw.lower() in all_titles and kw not in extracted_kws:
                    extracted_kws.append(kw)
                if len(extracted_kws) >= 6:
                    break
            if len(extracted_kws) >= 6:
                break

    _NEWS_CACHE = news_df
    _MRI_CACHE  = {
        'mri':          round(today, 4),
        'grade':        grade,
        'color':        color,
        'category':     cat,
        'top_category': cat,
        'top_keywords': extracted_kws,
        'sub_indices':  {k: round(v, 4) for k, v in sub.items()},
        'data_source':  data_source,   # 'realtime' | 'simulation'
        'news_count':   news_count,    # 실뉴스 기사 수 (0이면 시뮬)
        'kcci_loaded':  freight_df is not None,
        'cached_at':    datetime.now().strftime('%Y-%m-%d %H:%M KST'),
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


# ══════════════════════════════════════════════════════════════════
# 엔드포인트
# ══════════════════════════════════════════════════════════════════

@app.get('/api/health')
def health():
    """서버 상태 확인."""
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}


# ── Step 2: MRI 현황 + 과거 유사사례 + LSTM ───────────────────────

@app.get('/api/mri')
def get_mri(refresh: bool = False):
    """
    현재 MRI 점수·등급·카테고리·하위지수 + 과거 유사사례 맥락 반환.
    뉴스 RSS 자동 수집 (feedparser 없으면 시뮬 데이터).
    ?refresh=true 시 캐시 무효화 후 재수집.
    창고 추천은 MRI 등급에 무관하게 항상 제공 (warehouse_available: true).
    """
    global _MRI_CACHE, _NEWS_CACHE
    if refresh:
        _MRI_CACHE = None
        _NEWS_CACHE = None
    data = _get_mri_data()
    news_kws = data.get('top_keywords', [])
    effective_cat = _effective_category(data['category'], news_kws, data.get('sub_indices', {}))
    risk_ctx = build_risk_context(data['mri'], effective_cat, news_keywords=news_kws)

    # 최근 해운 뉴스 헤드라인 (최대 5건, _NEWS_CACHE에서 추출)
    recent_news: list[dict] = []
    if _NEWS_CACHE is not None and not _NEWS_CACHE.empty:
        for _, row in _NEWS_CACHE.head(5).iterrows():
            title = str(row.get('title', ''))
            if title and title.lower() not in ('nan', ''):
                recent_news.append({
                    'title':    title[:100],
                    'source':   str(row.get('source', '')),
                    'pub_date': str(row.get('pub_date', '')),
                    'category': str(row.get('pred_category', '')),
                })

    return {
        **data,
        'current_issue':        risk_ctx.current_issue,
        'top_keywords':         risk_ctx.top_keywords or news_kws,
        'recent_news':          recent_news,
        'avg_delay_days':       risk_ctx.avg_delay_days,
        'avg_freight_change':   risk_ctx.avg_freight_change_pct,
        'advisory_note':        risk_ctx.advisory_note,
        'warehouse_available':  True,   # MRI 무관, 모든 고객 이용 가능
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
    화주 출하 등록 → 과거 유사사례 + 현재 이슈 기반 참고 정보 반환.
    강제 시나리오 없음 — 화주가 A/B/C 시나리오 중 직접 결정합니다.
    """
    mri_data = _get_mri_data()
    mri      = mri_data['mri']
    category = mri_data['category']
    news_kws = mri_data.get('top_keywords', [])

    # 리스크 맥락 구성 (과거 유사사례 + 현재 이슈 요약)
    risk_ctx = build_risk_context(mri, category, news_keywords=news_kws)

    if req.route not in ROUTE_INFO:
        raise HTTPException(400, f'알 수 없는 항로: {req.route}')

    info     = ROUTE_INFO[req.route]
    est_cost = round((info['usd_per_teu'] / 33) * 1.5 * req.cbm)

    ship = {
        'shipment_id':    f'SH-{datetime.now().strftime("%H%M%S")}',
        'company':        req.company,
        'route':          req.route,
        'cargo_type':     req.cargo_type,
        'region':         req.region,
        'pickup_date':    datetime.strptime(req.pickup_date, '%Y-%m-%d'),
        'cbm':            req.cbm,
        'deadline_days':  req.deadline_days,
        'urgent':         req.urgent,
        'estimated_cost': est_cost,
    }

    # 과거 유사사례 평균값 기반 참고 추정
    ia = estimate_impact_advisory(ship, risk_ctx)

    route_to_port = {
        '부산→로테르담': '부산항(북항)',
        '부산→LA':       '부산항(북항)',
        '부산→상하이':   '부산항(북항)',
        '부산→싱가포르': '부산 신항',
        '부산→도쿄':     '부산항(북항)',
    }
    return {
        'shipment_id':    ship['shipment_id'],
        'estimated_cost': est_cost,
        'cargo_type':     req.cargo_type,
        'cbm':            req.cbm,
        'region':         req.region,
        # 현재 이슈
        'current_issue':  risk_ctx.current_issue,
        'top_keywords':   risk_ctx.top_keywords,
        'mri':            mri,
        'grade':          risk_ctx.grade,
        # 과거 유사사례 참고
        'similar_events':              risk_ctx.similar_events,
        'avg_historical_delay_days':   risk_ctx.avg_delay_days,
        'avg_historical_freight_change_pct': risk_ctx.avg_freight_change_pct,
        'advisory_note':               risk_ctx.advisory_note,
        # 이번 출하 참고 추정 (확정값 아님)
        'estimated_delay_days': ia.delay_days_applied,
        'estimated_cost_delta': ia.cost_delta,
        'deadline_at_risk':     ia.deadline_violated,
        'priority_cargo':       ia.requires_priority,
        'warehouse_recommended': risk_ctx.warehouse_recommended,
        'new_pickup_date':      ia.new_pickup_date.strftime('%Y-%m-%d'),
        'departure_port':       route_to_port.get(req.route, '부산항(북항)'),
    }


# ── Step 3: 창고 추천 (거리 기반 5곳) + 시나리오 A/B/C 비용 비교 ──

@app.post('/api/warehouse/recommend')
def warehouse_recommend(req: WarehouseRequest):
    """
    항만 인근 창고 5곳 추천 (거리 기반, MRI 무관 — 모든 고객 이용 가능) +
    시나리오 A/B/C 비용 비교.
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

    # 목적지(항만) 좌표 기준 5곳 추천
    dest_lat, dest_lng = PORT_COORDINATES.get(req.port_name, (35.1028, 129.0355))
    warehouses = recommend_nearest_five(
        dest_lat=dest_lat, dest_lng=dest_lng,
        cargo_type=cargo_enum, port_name=req.port_name, top_n=5,
    )

    # 시나리오 A/B/C 비용 비교
    scenarios = calc_scenarios(cbm=req.cbm, delay_days=req.delay_days)

    return {
        'warehouses': [
            {
                'id':             w.get('id', ''),
                'name':           w.get('name', ''),
                'address':        w.get('address', ''),
                'phone':          w.get('phone', '전화 문의'),
                'type':           w.get('type', '창고'),
                'bonded':         w.get('bonded'),
                'cold_chain':     w.get('cold_chain'),
                'hazmat_license': w.get('hazmat_license'),
                'area_sqm':       w.get('area_sqm'),
                'source':         w.get('source', 'NLIC'),
                'distance_km':    w.get('distance_km'),
                'duration_min':   w.get('duration_min'),
                'operating_hours': w.get('operating_hours', ''),
                'notes':          w.get('notes') or w.get('special_notes', ''),
            }
            for w in warehouses
        ],
        'scenarios': [scenario_to_dict(s) for s in scenarios],
        'scenario_note': (
            f'CBM={req.cbm}, 예상 지연={req.delay_days}일 기준 시뮬레이션 단가 적용 결과. '
            '실제 창고 가격 문의 후 /api/warehouse/calc_cost 로 정확한 비용 산출 가능.'
        ),
    }


@app.get('/api/warehouse/calc_cost')
def calc_warehouse_cost(
    warehouse_id: str,
    user_daily_krw: int,
    cbm: float,
    delay_days: int,
):
    """화주가 전화 문의로 얻은 실제 가격으로 총 예상 비용 계산."""
    result = calc_total_with_user_price(
        warehouse_id=warehouse_id,
        user_daily_krw=user_daily_krw,
        cbm=cbm,
        delay_days=delay_days,
    )
    return result


# ── Step 4: 루티 JSON 생성 ────────────────────────────────────────

@app.post('/api/routy/generate')
def generate_routy(req: RoutyJsonRequest):
    """
    Phase 1 루티 JSON 생성 (출발지 → 보세창고).
    Phase 2(창고→CY)는 화주가 선적 재개 시점 결정 후 별도 운송 지시.
    """
    wh = {
        'name':            req.warehouse_name,
        'address':         req.warehouse_address,
        'phone':           '',
        'type':            '창고',
        'distance_km':     req.warehouse_km,
        'duration_min':    req.warehouse_minutes,
        'special_notes':   '',
        'operating_hours': req.warehouse_hours,
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
    )
    return {'phase1': phase1}


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
