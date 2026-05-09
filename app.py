"""
app.py — 위밋모빌리티 해상 리스크 대응 플랫폼 웹앱
실행: streamlit run app.py

기능:
  탭 1. 리스크 모니터링 대시보드 (MRI + 뉴스)
  탭 2. LLM 자동 보고서 (Claude Haiku)
  탭 3. 화주 출하 요청
  탭 4. 시나리오 재조정 & 루티 JSON
"""
import os
import sys
import json
import random
import warnings
from pathlib import Path
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ── 한글 폰트 ─────────────────────────────────────────────────────────────────
def _setup_font():
    for name in ['Malgun Gothic', 'AppleGothic', 'NanumGothic']:
        if name in {f.name for f in fm.fontManager.ttflist}:
            plt.rcParams['font.family'] = name
            plt.rcParams['axes.unicode_minus'] = False
            return
    plt.rcParams['axes.unicode_minus'] = False

_setup_font()
np.random.seed(42)
random.seed(42)

# ── 시드 임포트 ───────────────────────────────────────────────────────────────
from src.config import SCENARIOS, ROUTE_INFO
from src.nlp_classifier import classify_news_df, top_category
from src.mri_engine import calc_today_mri, build_mri_series, mri_grade
from src.scenario_engine import auto_classify_scenario, generate_shipments, analyze_all
from src.reorganizer import reorganize_pickups
from src.routy_adapter import generate_routy_input, save_routy_json
from src.llm_reporter import generate_risk_report, estimate_monthly_cost, active_llm_provider
from src.data_loader import load_kcci
from src.historical_matcher import find_similar_events
from src.odcy_recommender import recommend_storage, CargoType
from src.option_presenter import generate_four_options, format_option_table, format_option_detail

# 화물유형 문자열 → CargoType enum 변환
_CARGO_TYPE_MAP = {
    '일반화물': CargoType.GENERAL,
    '냉장화물': CargoType.REFRIGERATED,
    '위험물':   CargoType.HAZMAT,
}
# 항로 → 출발 항만
_ROUTE_TO_PORT = {
    '부산→로테르담': '부산항(북항)',
    '부산→LA':       '부산항(북항)',
    '부산→상하이':   '부산항(북항)',
    '부산→싱가포르': '부산 신항',
    '부산→도쿄':     '부산항(북항)',
}
MRI_WAREHOUSE_THRESHOLD = 0.5   # 이 이상이면 창고 추천 활성화

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title='위밋모빌리티 — 해상 리스크 대응 플랫폼',
    page_icon='🚢',
    layout='wide',
    initial_sidebar_state='expanded',
)

# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image('https://via.placeholder.com/200x60?text=WEMET+MOBILITY', use_container_width=True)
    st.markdown('---')
    st.markdown('### 🔑 API 상태')

    def _key_badge(env: str, label: str):
        v = os.environ.get(env, '')
        ok = bool(v and not v.startswith('여기에'))
        st.markdown(f'{"✅" if ok else "❌"} **{label}**')

    _key_badge('GEMINI_API_KEY',     'Gemini API (무료, 우선)')
    _key_badge('ANTHROPIC_API_KEY', 'Claude API (유료, 대안)')
    _key_badge('ECOS_API_KEY',      'ECOS (한국은행)')
    _key_badge('BPA_API_KEY',       'BPA (부산항만공사)')

    # KCCI XLS 상태
    st.markdown('---')
    st.markdown('### 📊 운임지수 (KCCI)')
    _kcci_csv = ROOT / 'data' / 'kcci_weekly.csv'
    _xls_dir  = ROOT / 'data' / 'freight_index'
    _xls_cnt  = len(list(_xls_dir.glob('*.xls*'))) if _xls_dir.exists() else 0
    if _kcci_csv.exists():
        import pandas as _pd
        _k = _pd.read_csv(_kcci_csv, encoding='utf-8-sig')
        st.markdown(f'✅ **실데이터** ({len(_k)}주)')
    elif _xls_cnt > 0:
        st.markdown(f'⚠️ XLS {_xls_cnt}개 → 합치기 필요')
        st.caption('터미널: python scripts/auto_update.py --combine-freight')
    else:
        st.markdown('❌ **시뮬** (XLS 없음)')
        st.caption('data/freight_index/ 에 XLS 저장')

    st.markdown('---')
    st.markdown('### ⚙️ 설정')
    scenario_override = st.selectbox(
        '시나리오 수동 선택',
        ['자동'] + list(SCENARIOS.keys()),
        help='자동: MRI + NLP 기반 자동 분류',
    )
    n_shipments = st.slider('출하 예정 건수', 10, 50, 30)

    st.markdown('---')
    cost = estimate_monthly_cost(calls_per_day=24)
    st.markdown('### 💰 LLM 비용 추정 (월)')
    st.markdown(f'**1시간 간격 자동 모니터링**')
    col1, col2 = st.columns(2)
    col1.metric('캐싱 없이', f'${cost["cost_no_cache"]}')
    col2.metric('캐싱 적용', f'${cost["cost_with_cache"]}',
                delta=f'-{cost["savings_pct"]}%')

# ── 헤더 ──────────────────────────────────────────────────────────────────────
st.title('🚢 위밋모빌리티 — 해상 리스크 대응형 공동 물류 플랫폼')
st.caption('중소 수출기업 출하 수요 자동 재조정 | 위밋 루티/루티프로 연계')

# ── 데이터 초기화 (캐시) ──────────────────────────────────────────────────────
@st.cache_data(ttl=86400)   # 1일 캐시 (LSTM 학습 비용 절감)
def _load_lstm_insight():
    """LSTM 기반 부산항 물동량 3개월 예측 — 하루 1회 캐시."""
    try:
        import pandas as _pd
        from src.lstm_forecaster import build_main_df, train_and_forecast, HORIZON
        from src.mri_engine import build_mri_series as _bms

        _dates = _pd.date_range('2020-01-01', '2026-04-01', freq='MS')
        _mri_s = _bms(_dates)
        _mdf   = build_main_df(_dates, _mri_s)
        _res   = train_and_forecast(_mdf, epochs=60)   # 빠른 추정용 epoch 감소

        _future = _res['future_real'].tolist()
        _mape   = float(_res['mape_3m'])
        _months = _pd.date_range('2026-04-01', periods=HORIZON, freq='MS')
        _labels = [m.strftime('%Y.%m') for m in _months]
        return {'values': _future, 'mape': _mape, 'labels': _labels}
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _load_news():
    """실시간 뉴스 수집 (1시간 캐시)."""
    try:
        from src.real_data_fetcher import fetch_maritime_news
        import feedparser  # noqa
        df = fetch_maritime_news(max_per_source=10, days_back=7)
        if not df.empty:
            return df
    except Exception:
        pass
    return pd.DataFrame([
        {'title': '홍해 후티 반군 공격 재개, 컨테이너 운임 급등',  'text': '홍해 항로 봉쇄로 운임 30% 상승 우려',   'source': '시뮬'},
        {'title': '부산항 컨테이너 처리량 사상 최대 갱신',         'text': '4월 처리량 전년 대비 4.8% 증가',         'source': '시뮬'},
        {'title': '태풍 카눈 북상, 부산항 입출항 차질 우려',        'text': '기상청 태풍 경보, 컨테이너선 피항 준비', 'source': '시뮬'},
        {'title': '미중 추가 관세 부과, 환적 물동량 감소',          'text': '관세 정책 변동으로 수출 기업 타격',      'source': '시뮬'},
        {'title': '호르무즈 해협 긴장 고조, 이란 미사일 위협',      'text': '지정학적 분쟁 위험 확대',               'source': '시뮬'},
        {'title': '부산항 노조 부분 파업, 하역 지연',               'text': '항만 파업으로 컨테이너 체류 시간 증가',  'source': '시뮬'},
        {'title': '글로벌 선사 운임 인상 발표',                     'text': 'Maersk, MSC 운임 5월부터 상승',         'source': '시뮬'},
        {'title': '한국 조선업 LNG선 수주 회복',                    'text': '글로벌 LNG선 발주 증가',               'source': '시뮬'},
        {'title': 'EU CBAM 본격 시행 임박, 수출기업 비상',          'text': 'CBAM 인증서 구매 부담 가중',            'source': '시뮬'},
        {'title': '부산항 신항 물동량 회복세',                      'text': '신항 정상화로 처리능력 향상',            'source': '시뮬'},
    ])

@st.cache_data(ttl=3600)
def _load_kcci_cached():
    """KCCI 주간 데이터 로드 (1시간 캐시). JSON 직렬화해서 반환."""
    df = load_kcci(ROOT / 'data', use_real=True)
    if df is not None:
        return df.to_json(orient='records')
    return None

@st.cache_data(ttl=3600)
def _compute_mri(news_df_json: str, freight_json: str | None):
    news_df    = pd.read_json(news_df_json, orient='records')
    news_df    = classify_news_df(news_df)
    freight_df = pd.read_json(freight_json, orient='records') if freight_json else None
    if freight_df is not None:
        freight_df['date'] = pd.to_datetime(freight_df['date'])
    dates  = pd.date_range('2020-01-01', '2026-04-01', freq='MS')
    series = build_mri_series(dates, freight_df)
    today  = calc_today_mri(news_df, freight_df)
    cat    = top_category(news_df)
    # @st.cache_data는 JSON 직렬화 가능 타입만 허용
    # pd.DatetimeIndex / np.ndarray → list 변환 필수
    return (
        news_df.to_json(orient='records'),
        dates.strftime('%Y-%m-%d').tolist(),
        series.tolist(),
        float(today),
        str(cat),
    )

# 데이터 로드
raw_news     = _load_news()
freight_json = _load_kcci_cached()
news_json, dates_list, mri_series_list, today_mri, today_cat = _compute_mri(
    raw_news.to_json(orient='records'), freight_json
)
news_df    = pd.read_json(news_json, orient='records')
dates      = pd.to_datetime(dates_list)
mri_series = np.array(mri_series_list)

today_grade_label, today_color = mri_grade(today_mri)

# 시나리오 결정
if scenario_override == '자동':
    scenario_id = auto_classify_scenario(today_mri, today_cat)
else:
    scenario_id = scenario_override
scenario = SCENARIOS[scenario_id]

# LSTM 부산항 예측 (1일 캐시 — PyTorch 없으면 None)
lstm_insight = _load_lstm_insight()

# 출하 + 영향 분석
ship_df   = generate_shipments(n=n_shipments)
impacts   = analyze_all(ship_df, scenario_id)
reorg     = reorganize_pickups(ship_df, impacts, scenario)
routy_out = generate_routy_input(scenario_id, scenario, ship_df, impacts, reorg)

# ── 탭 구성 ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    '📡 리스크 모니터링',
    '🤖 LLM 자동 보고서',
    '📦 출하 요청',
    '🔀 시나리오 재조정',
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — 리스크 모니터링
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader('Maritime Risk Index (MRI) 현황')

    col1, col2, col3, col4 = st.columns(4)
    col1.metric('MRI 점수', f'{today_mri:.3f}', help='0~1, 높을수록 위험')
    col2.metric('등급', today_grade_label)
    col3.metric('주요 카테고리', today_cat)
    col4.metric('자동 분류 시나리오', f'{scenario["icon"]} {scenario_id.split("_")[0]}')

    st.markdown('---')

    # MRI 시계열 차트
    mri_df = pd.DataFrame({'date': dates, 'mri': mri_series})
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.plot(mri_df['date'], mri_df['mri'], color='#1F4E79', linewidth=2)
    ax.fill_between(mri_df['date'], 0, mri_df['mri'], alpha=0.2, color='#1F4E79')
    ax.axhline(0.8, color='#EF5350', linestyle='--', alpha=0.6, label='위험(0.8)')
    ax.axhline(0.6, color='#FF7043', linestyle='--', alpha=0.6, label='경계(0.6)')
    ax.axhline(0.3, color='#FFA726', linestyle='--', alpha=0.6, label='주의(0.3)')
    ax.axhline(today_mri, color='#1565C0', linewidth=2.5,
               label=f'현재 MRI={today_mri:.3f}')
    ax.set_ylabel('MRI')
    ax.set_ylim(0, 1)
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_title('해상 리스크 지수 시계열 (2020~2026)')
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    st.markdown('---')

    # ── MRI 설명 + 과거 유사사례 인사이트 (Step 2) ───────────────────────────
    with st.expander('📖 MRI(해상 리스크 지수)란?', expanded=today_mri >= 0.5):
        st.markdown(f"""
**MRI(Maritime Risk Index)** 는 위밋모빌리티가 실시간 해사 뉴스, 운임지수, 해협 통행량 데이터를
AHP(계층분석법)로 가중 합산한 **0~1 사이 해상 리스크 종합 지표**입니다.

| 등급 | MRI 범위 | 의미 |
|---|---|---|
| 🔴 위험 | 0.8 이상 | 항로 봉쇄·전쟁 수준 — 즉각 대응 필요 |
| 🟠 경계 | 0.6~0.8 | 심각한 운임 상승·지연 예상 |
| 🟡 주의 | 0.3~0.6 | 파업·혼잡·소규모 분쟁 |
| 🟢 정상 | 0.3 미만 | 정상 운항 범위 |

**현재 MRI {today_mri:.3f}** 와 유사했던 과거 사례:
        """)
        with st.spinner('과거 유사사례 분석 중...'):
            _cats = [today_cat] if today_cat != '정상' else ['지정학분쟁']
            _similar = find_similar_events(today_mri, _cats, top_k=3)
        if _similar:
            avg_delay   = sum(e['avg_delay_days']           for e in _similar) / len(_similar)
            avg_freight = sum(e['avg_freight_increase_pct'] for e in _similar) / len(_similar)
            col1, col2 = st.columns(2)
            col1.metric('유사사례 평균 지연', f'+{avg_delay:.1f}일')
            col2.metric('유사사례 평균 운임 상승', f'+{avg_freight:.1f}%')
            for ev in _similar:
                st.markdown(f"**{ev['rank']}위** {ev['name']} ({ev['date'][:4]}년) — "
                            f"지연 {ev['avg_delay_days']}일, 운임 +{ev['avg_freight_increase_pct']}%")

    # ── LSTM 부산항 물동량 예측 인사이트 (Step 2) ────────────────────────────
    st.markdown('---')
    st.subheader('📈 부산항 물동량 예측 (LSTM)')
    if lstm_insight:
        _vals   = lstm_insight['values']
        _labels = lstm_insight['labels']
        _mape   = lstm_insight['mape']
        col1, col2, col3 = st.columns(3)
        for _col, _label, _val in zip([col1, col2, col3], _labels, _vals):
            _base = 200.0
            _delta_pct = (_val - _base) / _base * 100
            _col.metric(
                label=f'{_label} 예측',
                value=f'{_val:.1f}만 TEU',
                delta=f'{_delta_pct:+.1f}% vs 평년',
            )
        st.caption(f'LSTM 검증 MAPE: {_mape:.1f}%  |  기준: 부산항 평년 200만 TEU/월')
        if today_mri >= 0.5:
            _avg = sum(_vals) / len(_vals)
            _drop = (_base - _avg) / _base * 100
            if _drop > 0:
                st.warning(f'⚠️ 현재 MRI {today_mri:.3f} — 향후 3개월 평균 물동량이 평년 대비 **{_drop:.1f}% 감소** 예상됩니다.')
            else:
                st.info(f'현재 MRI {today_mri:.3f} — 향후 3개월 물동량은 평년 수준 유지 예상.')
    else:
        st.info('LSTM 예측 불가 (PyTorch 미설치 또는 데이터 부족). `pip install torch` 후 재시작하세요.')

    st.markdown('---')
    st.subheader('📰 실시간 해사 뉴스')
    sources = news_df.get('source', pd.Series(['알 수 없음']*len(news_df))).unique()
    st.caption(f'수집 소스: {", ".join(sources)}')

    for _, row in news_df.head(8).iterrows():
        w = row.get('risk_weight', 0)
        icon = '🔴' if w >= 0.8 else ('🟠' if w >= 0.6 else ('🟡' if w >= 0.4 else '🟢'))
        cat  = row.get('pred_category', '')
        with st.expander(f'{icon} {row["title"]}'):
            st.write(row.get('text', ''))
            if cat:
                st.caption(f'카테고리: {cat} | 리스크 가중치: {w:.2f}')

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LLM 자동 보고서
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader('🤖 Claude AI 해상 리스크 자동 보고서')

    provider = active_llm_provider()
    llm_ready = provider != '미설정'

    col1, col2 = st.columns([2, 1])
    with col1:
        st.info(
            f'**현재 LLM**: {provider}  \n'
            '실제 서비스: 1시간 간격 자동 생성 → 화주 이메일/대시보드 발송'
        )
    with col2:
        if not llm_ready:
            st.warning(
                '⚠️ API 키 없음  \n'
                '**무료**: GEMINI_API_KEY  \n'
                'aistudio.google.com'
            )

    if st.button('보고서 생성', disabled=not llm_ready, type='primary'):
        headlines = news_df['title'].head(8).tolist()
        affected  = sum(1 for ia in impacts if ia.is_affected)
        cost_delta = sum(ia.cost_delta for ia in impacts)

        report_area = st.empty()
        full_text   = ''
        with st.spinner('보고서 생성 중...'):
            for chunk in generate_risk_report(
                today_mri=today_mri,
                mri_grade=today_grade_label,
                top_category=today_cat,
                scenario_id=scenario_id,
                scenario_name=scenario['name'],
                news_headlines=headlines,
                affected_count=affected,
                cost_delta=cost_delta,
            ):
                full_text += chunk
                report_area.markdown(full_text + '▌')
        report_area.markdown(full_text)
        st.success(f'✅ 보고서 생성 완료 — {datetime.now().strftime("%H:%M:%S")}')

    if not llm_ready:
        st.markdown('---')
        st.markdown('**샘플 보고서 미리보기** (실제 보고서와 유사):')
        st.markdown(f"""
## 🚨 오늘의 해상 리스크 현황
**MRI 등급**: {today_grade_label} ({today_mri:.3f})
**핵심 리스크**: {today_cat} 카테고리 이슈 감지. 시나리오 **{scenario['name']}** 발동.

## 📋 화주 권고 행동
1. **즉시**: 출항 {scenario['delay_days']}일 지연 가능성 대비 — 납기 여유 확인
2. **준비**: 운임 +{scenario['freight_surge_pct']:.0%} 상승분 견적서 재검토

## 📊 시나리오 전망
{scenario['description']}
        """)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — 화주 출하 요청
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader('📦 출하 예정 등록')
    st.caption('화주가 위밋모빌리티에 선적을 요청하는 인터페이스')

    with st.form('shipment_form'):
        col1, col2 = st.columns(2)
        with col1:
            company   = st.text_input('화주명 (회사명)', placeholder='예) (주)경기식품')
            region    = st.selectbox('집화 권역', ['경기남부', '경기북부', '충청', '경상남부', '경상북부'])
            cargo     = st.selectbox('화물 유형', ['일반화물', '냉장화물', '위험물'])
        with col2:
            route     = st.selectbox('희망 항로', list(ROUTE_INFO.keys()))
            cbm       = st.number_input('화물 용량 (CBM)', min_value=1.0, max_value=100.0, value=15.0)
            deadline  = st.selectbox('납기 여유 (일)', [7, 10, 14, 21])

        pickup_date = st.date_input('희망 집화일', value=datetime.today() + timedelta(days=5))
        urgent      = st.checkbox('긴급 화물 (냉장/특수 우선처리 요청)')
        note        = st.text_area('특이사항', placeholder='온도 관리 요구사항, 위험물 분류 등')

        submitted = st.form_submit_button('✅ 출하 등록 & 시나리오 분석', type='primary')

    if submitted and company:
        info = ROUTE_INFO[route]
        est_cost = round((info['usd_per_teu'] / 33) * 1.5 * cbm)

        new_ship = {
            'shipment_id':   f'SH-REQ-{datetime.now().strftime("%H%M%S")}',
            'company':       company,
            'route':         route,
            'cargo_type':    cargo,
            'region':        region,
            'pickup_date':   datetime.combine(pickup_date, datetime.min.time()),
            'cbm':           float(cbm),
            'deadline_days': int(deadline),
            'urgent':        urgent,
            'estimated_cost': est_cost,
        }

        from src.scenario_engine import analyze_impact
        ia = analyze_impact(new_ship, scenario)

        st.success(f'✅ 등록 완료: {new_ship["shipment_id"]}')

        # ── Step 2: 화주에게 현재 MRI 맥락 제공 ─────────────────────────────
        with st.expander(f'📊 현재 해상 리스크 현황 — MRI {today_mri:.3f} [{today_grade_label}]', expanded=True):
            _c1, _c2, _c3 = st.columns(3)
            _c1.metric('MRI 등급', today_grade_label)
            _c2.metric('주요 리스크', today_cat)
            _c3.metric('예상 지연', f'+{scenario["delay_days"]}일')

            _cats2 = [today_cat] if today_cat != '정상' else ['지정학분쟁']
            _sim2  = find_similar_events(today_mri, _cats2, top_k=2)
            if _sim2:
                _avg_d = sum(e['avg_delay_days']           for e in _sim2) / len(_sim2)
                _avg_f = sum(e['avg_freight_increase_pct'] for e in _sim2) / len(_sim2)
                st.markdown(
                    f'**과거 유사 MRI 수준에서의 평균 영향**: '
                    f'지연 +**{_avg_d:.1f}일**, 운임 +**{_avg_f:.1f}%**'
                )
                for _ev in _sim2:
                    st.caption(f"참고: {_ev['name']} ({_ev['date'][:4]}년) — "
                               f"지연 {_ev['avg_delay_days']}일, 운임 +{_ev['avg_freight_increase_pct']}%")

            if lstm_insight:
                _avg_vol = sum(lstm_insight['values']) / len(lstm_insight['values'])
                _drop_vol = (200.0 - _avg_vol) / 200.0 * 100
                if _drop_vol > 0:
                    st.caption(f'📈 LSTM 예측: 향후 3개월 부산항 물동량 평년 대비 {_drop_vol:.1f}% 감소 예상')

        col1, col2, col3, col4 = st.columns(4)
        col1.metric('예상 운임', f'${est_cost:,}')
        col2.metric('지연 예상', f'+{ia.delay_days_applied}일')
        col3.metric('운임 변화', f'${ia.cost_delta:+,}')
        col4.metric('납기 위반', '⚠️ 위험' if ia.deadline_violated else '✅ 안전')

        if ia.requires_priority:
            st.info(f'⭐ **우선처리 대상** — {cargo}화물로 자동 우선 분류됩니다.')
        if ia.requires_holdback:
            st.warning('◐ **항만 반입 보류 권고** — 출항 지연 대비 내륙 보관을 권장합니다.')

        st.json({
            'shipment_id': new_ship['shipment_id'],
            'action':      'PRIORITY' if ia.requires_priority else ('HOLDBACK' if ia.requires_holdback else 'SHIFT'),
            'new_pickup':  ia.new_pickup_date.strftime('%Y-%m-%d'),
            'reason':      ia.reason,
        })

        # ── Step 3: MRI 임계값 이상이면 창고·ODCY 추천 + 4가지 옵션 ──────────
        if today_mri >= MRI_WAREHOUSE_THRESHOLD:
            st.markdown('---')
            st.subheader('🏭 Step 3. 항만 주변 창고·ODCY 자동 추천')
            st.caption(
                f'현재 MRI {today_mri:.3f} ≥ {MRI_WAREHOUSE_THRESHOLD} — '
                '창고 임시 보관 옵션을 제시합니다. **최종 결정은 화주님께 있습니다.**'
            )

            _cargo_enum = _CARGO_TYPE_MAP.get(cargo, CargoType.GENERAL)
            _port       = _ROUTE_TO_PORT.get(route, '부산항(북항)')
            _kakao_key  = os.environ.get('KAKAO_REST_API_KEY', '')
            _mobi_key   = os.environ.get('KAKAO_MOBILITY_KEY', '')

            with st.spinner(f'카카오 API로 {_port} 주변 창고 탐색 중...'):
                _storage = recommend_storage(
                    port_name=_port,
                    cargo_type=_cargo_enum,
                    top_n=3,
                    kakao_rest_key=_kakao_key or None,
                    kakao_mobility_key=_mobi_key or None,
                )

            _mode_label = '카카오 실데이터' if not _storage['simulation_mode'] else '시뮬레이션 DB'
            st.caption(f'데이터 소스: {_mode_label}')

            # 창고 목록 표시
            _recs = _storage['recommendations']['comprehensive']
            if _recs:
                for _w in _recs[:3]:
                    with st.expander(f"🏭 {_w['name']} ({_w['distance_km']}km)"):
                        col1, col2, col3 = st.columns(3)
                        col1.write(f"**주소**: {_w['address']}")
                        col2.write(f"**거리**: {_w['distance_km']}km / {_w['duration_min']}분")
                        col3.write(f"**운영**: {_w.get('operating_hours', '-')}")
                        if _w.get('special_notes'):
                            st.warning(_w['special_notes'])

            # 4가지 옵션 비교
            st.markdown('---')
            st.subheader('💡 A/B/C/D 4가지 대응 옵션')
            _shipment_dict = {
                'cargo_type': cargo, 'cbm': float(cbm), 'region': region
            }
            _options = generate_four_options(
                shipment=_shipment_dict,
                storage_result=_storage,
                delay_days=ia.delay_days_applied or scenario['delay_days'],
                freight_usd=est_cost,
            )

            # 옵션 카드 표시
            _cols = st.columns(4)
            for _i, (_col, _opt) in enumerate(zip(_cols, _options)):
                with _col:
                    _delta = f"-${abs(_opt.savings_vs(_options[0])):,.0f}" if _i > 0 else "기준"
                    _col.metric(
                        label=f'{_opt.option_id}안: {_opt.option_name[:10]}',
                        value=f'${_opt.total_usd:,.0f}',
                        delta=_delta if _i > 0 else None,
                    )

            # D안 상세
            _opt_d = next((o for o in _options if o.option_id == 'D'), _options[-1])
            with st.expander('★ D안 (권장) 상세 보기'):
                st.text(format_option_detail(_opt_d, _options[0]))

            # 루티 JSON 생성 버튼
            if st.button('📤 루티 연계 JSON 생성 (D안 선택)', type='primary'):
                from src.storage_routy_adapter import generate_storage_routy_json, save_storage_json
                _top_wh = _recs[0] if _recs else {}
                _p1 = generate_storage_routy_json(
                    shipment_id=new_ship['shipment_id'],
                    company=company, region=region,
                    cargo_type=cargo, cbm=float(cbm),
                    cold_chain=(cargo == '냉장화물'), hazmat=(cargo == '위험물'),
                    origin_address=f'{region} 출고지',
                    original_port=_port,
                    original_pickup_date=pickup_date.strftime('%Y-%m-%d'),
                    mri_current=today_mri,
                    delay_reason=scenario['name'],
                    recommended_warehouse=_top_wh,
                )
                _fp = save_storage_json(_p1, ROOT / 'routy_inputs')
                import json as _json
                st.download_button(
                    '⬇️ Phase 1 JSON 다운로드',
                    data=_json.dumps(_p1, ensure_ascii=False, indent=2, default=str),
                    file_name=_fp.name, mime='application/json',
                )
                st.success(f'루티 JSON 생성 완료: {_fp.name}')
        else:
            st.info(f'현재 MRI {today_mri:.3f} < {MRI_WAREHOUSE_THRESHOLD} — 평상시 운영 범위. 창고 보관 불필요.')

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — 시나리오 재조정 & 루티 JSON
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader(f'{scenario["icon"]} 시나리오 재조정 결과')
    st.caption(f'**{scenario_id}** — {scenario["description"]}')

    # KPI 요약
    affected    = sum(1 for ia in impacts if ia.is_affected)
    violated    = sum(1 for ia in impacts if ia.deadline_violated)
    total_delta = sum(ia.cost_delta for ia in impacts)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('총 출하', f'{len(ship_df)}건')
    col2.metric('영향 건수', f'{affected}건')
    col3.metric('납기 위반', f'{violated}건', delta=None)
    col4.metric('운임 변화', f'${total_delta:+,}')
    col5.metric('권역 통합', f'{len(reorg["consolidation_groups"])}그룹')

    st.markdown('---')
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('**행동 분류**')
        action_labels = ['우선처리\n(PRIORITY)', '반입보류\n(HOLDBACK)', '집화이동\n(SHIFT)']
        action_vals   = [len(reorg['pickup_priority']),
                         len(reorg['pickup_holdback']),
                         len(reorg['pickup_shifted'])]
        fig, ax = plt.subplots(figsize=(5, 3))
        colors = ['#D32F2F', '#F57C00', '#2E75B6']
        bars = ax.bar(action_labels, action_vals, color=colors, edgecolor='black')
        for bar, val in zip(bars, action_vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                        str(val), ha='center', fontweight='bold')
        ax.set_ylabel('건수')
        ax.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

    with col2:
        st.markdown('**권역 통합 그룹**')
        if reorg['consolidation_groups']:
            for g in reorg['consolidation_groups'][:5]:
                st.markdown(
                    f'**{g["region"]}** / {g["cargo_type"]}  \n'
                    f'{", ".join(g["companies"])}  \n'
                    f'📅 {g["merged_pickup_date"]}  총 {g["total_cbm"]}CBM'
                )
                st.markdown('---')
        else:
            st.info('권역 통합 대상 없음')

    st.markdown('---')
    st.subheader('📤 루티 API 입력 JSON')
    st.caption('위밋 루티/루티프로가 즉시 활용 가능한 배차 최적화 입력값')

    col1, col2 = st.columns([1, 1])
    with col1:
        st.json(routy_out['summary'])
    with col2:
        st.json(routy_out['scenario'])

    routy_dir = ROOT / 'routy_inputs'
    routy_dir.mkdir(exist_ok=True)
    fp = save_routy_json(routy_out, routy_dir)

    with open(fp, encoding='utf-8') as f:
        json_str = f.read()

    st.download_button(
        label='⬇️ JSON 다운로드',
        data=json_str,
        file_name=fp.name,
        mime='application/json',
        type='primary',
    )
    st.caption(f'저장 경로: {fp}')

    # 5개 시나리오 비교
    st.markdown('---')
    st.subheader('📊 5개 시나리오 비교')
    with st.spinner('전체 시나리오 분석 중...'):
        from src.routy_adapter import run_all_scenarios
        all_results = run_all_scenarios(ship_df, SCENARIOS)

    comparison_data = []
    for sid, res in all_results.items():
        s  = res['routy_input']['summary']
        sc = res['scenario']
        comparison_data.append({
            '시나리오': f'{sc["icon"]} {sid.split("_")[0]} {sc["name"][:12]}',
            '영향 건수': s['affected'],
            '우선처리':  s['priority'],
            '반입보류':  s['holdback'],
            '집화이동':  s['shifted'],
            '권역통합':  s['consolidation_groups'],
            '비용변화($)': s['total_cost_delta_usd'],
        })
    st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, hide_index=True)
