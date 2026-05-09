"""
auto_update.py — 데이터 자동 갱신 통합 스크립트

실행 방법:
  python scripts/auto_update.py --mode daily    # 매일: 환율·유가
  python scripts/auto_update.py --mode weekly   # 매주: 운임지수·뉴스
  python scripts/auto_update.py --mode monthly  # 매월: 물동량·전체
  python scripts/auto_update.py --combine-freight  # 수동: 운임지수 XLS 합치기

[자동 갱신 주기별 항목]
  일별 (Daily):
    - USD/KRW 환율   frankfurter.app (무료·키 불필요)
    - Brent 유가     FRED 미국 연방준비제도 (무료·키 불필요)
    - ECOS 공식값    ECOS_API_KEY 있으면 덮어씀

  주별 (Weekly):
    - 해사 뉴스RSS   gCaptain / Splash247 / 한국해운신문
    - 운임지수 XLS   data/freight_index/ 폴더 갱신 (자동 합치기)
    - KCCI API      DATA_GO_KR_KEY 있으면 시도

  월별 (Monthly):
    - 부산항 물동량  NLIC 자동 시도 → 실패 시 수동 안내
    - 전체 캐시 갱신
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

logging.basicConfig(
    level=logging.WARNING,          # WARNING 이상만 콘솔 출력 (INFO는 로그에만)
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('auto_update')

DATA_DIR    = ROOT / 'data'
CACHE_DIR   = ROOT / 'data' / 'ecos_cache'
NLIC_DIR    = ROOT / 'data' / 'nlic_raw'
FREIGHT_DIR = ROOT / 'data' / 'freight_index'
LOG_DIR     = ROOT / 'data' / 'update_logs'

for d in [DATA_DIR, CACHE_DIR, NLIC_DIR, FREIGHT_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

_results: dict[str, dict] = {}


def _record(name: str, status: str, detail: str = '') -> None:
    _results[name] = {'status': status, 'detail': detail,
                      'time': datetime.now().strftime('%H:%M:%S')}
    icon = {'OK': '✅', 'WARN': '⚠️', 'FAIL': '❌'}.get(status, '?')
    print(f'  {icon} {name:<18s} {detail}')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DAILY — 환율 · 유가
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _update_exchange_rate_daily() -> None:
    """오늘 환율 → data/today_rates.json 저장 + 월별 CSV 업데이트."""
    import requests

    today = datetime.today().strftime('%Y-%m-%d')
    rate  = None

    # 1. frankfurter.app (무료, 실시간)
    try:
        resp = requests.get(
            'https://api.frankfurter.app/latest?from=USD&to=KRW',
            timeout=10
        )
        resp.raise_for_status()
        rate = resp.json()['rates']['KRW']
        _record('환율 (오늘)', 'OK', f'${1:,.0f} = ₩{rate:,.0f}  [frankfurter]')
    except Exception as e:
        logger.debug('frankfurter 환율 실패: %s', e)

    # 2. ECOS 공식 (오늘 데이터가 있으면 덮어씀)
    ecos_key = os.environ.get('ECOS_API_KEY', '')
    if ecos_key:
        try:
            from src.real_data_fetcher import fetch_ecos_exchange_rate
            ym = datetime.today().strftime('%Y%m')
            df = fetch_ecos_exchange_rate(ym, ym)   # 이번 달만
            if df is not None and not df.empty:
                rate = float(df['exchange_rate'].iloc[-1])
                _record('환율 (ECOS)', 'OK', f'₩{rate:,.0f}/USD (공식)')
        except Exception as e:
            logger.debug('ECOS 환율 실패: %s', e)

    if rate is None:
        _record('환율', 'FAIL', 'frankfurter + ECOS 모두 실패')
        return

    # today_rates.json 저장 (앱에서 실시간 사용)
    rates_fp = DATA_DIR / 'today_rates.json'
    try:
        prev = json.loads(rates_fp.read_text(encoding='utf-8')) if rates_fp.exists() else {}
    except Exception:
        prev = {}
    prev[today] = {'usd_krw': rate}
    rates_fp.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding='utf-8')

    # 월별 환율 CSV 업데이트 (캐시 갱신)
    try:
        from src.real_data_fetcher import fetch_exchange_rate_monthly
        df = fetch_exchange_rate_monthly(start='2020-01-01')
        if df is not None:
            df.to_csv(DATA_DIR / 'ecos_cache' / 'fx_monthly.csv',
                      index=False, encoding='utf-8-sig')
    except Exception:
        pass


def _update_oil_price_daily() -> None:
    """오늘 Brent 유가 → data/today_rates.json 저장 + 월별 CSV 업데이트."""
    import requests
    from io import StringIO
    import pandas as pd

    today = datetime.today().strftime('%Y-%m-%d')
    price = None
    source = ''

    # 1. Yahoo Finance BZ=F (일별 실시간, 무료·키 불필요)
    try:
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/BZ%3DF?range=5d&interval=1d'
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        resp.raise_for_status()
        result = resp.json().get('chart', {}).get('result', [])
        if result:
            closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
            closes = [c for c in closes if c is not None]
            if closes:
                price  = round(float(closes[-1]), 2)
                source = 'Yahoo Finance'
                _record('유가 (오늘)', 'OK', f'Brent ${price:.2f}/배럴  [Yahoo]')
    except Exception as e:
        logger.debug('Yahoo Finance 유가 실패: %s', e)

    # 2. FRED DCOILBRENTEU (일별, 무료) — Yahoo 실패 시
    if price is None:
        try:
            resp = requests.get(
                'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU',
                timeout=20
            )
            resp.raise_for_status()
            df = pd.read_csv(StringIO(resp.text))
            df.columns = ['date', 'oil_price']   # observation_date, DCOILBRENTEU
            df['date']      = pd.to_datetime(df['date'], errors='coerce')
            df['oil_price'] = pd.to_numeric(df['oil_price'], errors='coerce')
            df = df.dropna().sort_values('date')
            if not df.empty:
                price  = round(float(df['oil_price'].iloc[-1]), 2)
                source = 'FRED'
                _record('유가 (오늘)', 'OK', f'Brent ${price:.2f}/배럴  [FRED]')
                df.to_csv(DATA_DIR / 'ecos_cache' / 'oil_daily.csv',
                          index=False, encoding='utf-8-sig')
        except Exception as e:
            logger.debug('FRED 유가 실패: %s', e)

    # 3. ECOS 두바이유 (월별 공식) — ECOS_API_KEY 있으면 추가 시도
    ecos_key = os.environ.get('ECOS_API_KEY', '')
    if ecos_key:
        try:
            from src.real_data_fetcher import fetch_ecos_oil_price
            ym = datetime.today().strftime('%Y%m')
            df = fetch_ecos_oil_price(ym, ym)
            if df is not None and not df.empty:
                price  = float(df['oil_price'].iloc[-1])
                source = 'ECOS'
                _record('유가 (ECOS)', 'OK', f'두바이유 ${price:.2f}/배럴 (공식)')
        except Exception as e:
            logger.debug('ECOS 유가 실패: %s', e)

    if price is None:
        _record('유가', 'FAIL', 'Yahoo/FRED/ECOS 모두 실패')
        return

    # today_rates.json 저장 (앱·노트북에서 실시간 가격 표시용)
    rates_fp = DATA_DIR / 'today_rates.json'
    try:
        prev = json.loads(rates_fp.read_text(encoding='utf-8')) if rates_fp.exists() else {}
    except Exception:
        prev = {}
    if today not in prev:
        prev[today] = {}
    prev[today]['brent_usd'] = price
    rates_fp.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding='utf-8')

    # 월별 히스토리 CSV 갱신 → LSTM이 매번 인터넷 없이 사용 가능
    try:
        from src.real_data_fetcher import fetch_brent_oil_monthly
        df_mo = fetch_brent_oil_monthly(start='2019-01-01')
        if df_mo is not None:
            df_mo.to_csv(DATA_DIR / 'ecos_cache' / 'oil_monthly.csv',
                         index=False, encoding='utf-8-sig')
            logger.debug('oil_monthly.csv 저장: %d행', len(df_mo))
    except Exception as e:
        logger.debug('oil_monthly.csv 저장 실패: %s', e)


def run_daily() -> None:
    print('\n[환율] USD/KRW 일별 갱신...')
    _update_exchange_rate_daily()
    print('\n[유가] Brent 일별 갱신...')
    _update_oil_price_daily()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEEKLY — 운임지수 · 뉴스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _update_news() -> None:
    try:
        from src.real_data_fetcher import fetch_maritime_news
        df = fetch_maritime_news(max_per_source=30, days_back=30)
        _record('해사뉴스', 'OK' if not df.empty else 'WARN',
                f'{len(df)}건' if not df.empty else '수집 결과 없음')
    except Exception as e:
        _record('해사뉴스', 'FAIL', str(e))


def _update_freight_indices() -> None:
    """
    운임지수 XLS 합치기 + (선택) KCCI API 갱신.
    XLS 파일이 새로 추가됐으면 자동으로 재합치기.
    """
    from src.freight_index_loader import combine_freight_excels, load_kcci_weekly

    xls_files = list(FREIGHT_DIR.glob('*.xls')) + list(FREIGHT_DIR.glob('*.xlsx'))
    csv_fp    = DATA_DIR / 'kcci_weekly.csv'

    if not xls_files:
        _record('운임지수 XLS', 'WARN',
                f'파일 없음 → {FREIGHT_DIR}/ 에 XLS 저장 후 --combine-freight 실행')
        return

    # XLS 중 가장 최신 수정일 확인
    latest_xls_mtime = max(fp.stat().st_mtime for fp in xls_files)
    csv_mtime = csv_fp.stat().st_mtime if csv_fp.exists() else 0

    if latest_xls_mtime > csv_mtime:
        # 새 파일 있음 → 재합치기
        df = combine_freight_excels(FREIGHT_DIR, csv_fp)
        if df is not None:
            _record('운임지수 XLS', 'OK',
                    f'{len(df)}주 ({df["date"].min().strftime("%Y.%m.%d")}~'
                    f'{df["date"].max().strftime("%Y.%m.%d")})')
        else:
            _record('운임지수 XLS', 'FAIL', 'XLS 파싱 실패')
    else:
        _record('운임지수 XLS', 'OK', f'최신 상태 유지 ({len(xls_files)}개 파일)')

    # KCCI API (선택)
    if os.environ.get('DATA_GO_KR_KEY'):
        try:
            from src.real_data_fetcher import fetch_kcci_api
            df = fetch_kcci_api()
            if df is not None:
                _record('KCCI API', 'OK', f'{len(df)}건')
        except Exception as e:
            _record('KCCI API', 'FAIL', str(e))


def run_weekly() -> None:
    print('\n[뉴스] 해사 뉴스 RSS 수집...')
    _update_news()
    print('\n[운임지수] KCCI/KUWI/KUEI XLS 갱신...')
    _update_freight_indices()
    # 주간 업데이트에 일별 업데이트 포함
    run_daily()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MONTHLY — 물동량 + 전체
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _update_throughput() -> None:
    from src.nlic_fetcher import download_nlic_range, combine_nlic_excels

    today    = datetime.today()
    prev2_y  = today.year if today.month > 2 else today.year - 1
    prev2_m  = (today.month - 2) % 12 or 12
    start_ym = f'{prev2_y}{prev2_m:02d}'
    end_ym   = today.strftime('%Y%m')

    fps = download_nlic_range(start_ym, end_ym, save_dir=NLIC_DIR)
    if fps:
        df = combine_nlic_excels(NLIC_DIR, DATA_DIR / 'busan_throughput.csv')
        if df is not None:
            _record('부산항물동량', 'OK',
                    f'NLIC: {len(df)}개월 → {(DATA_DIR/"busan_throughput.csv").name}')
            return

    _record('부산항물동량', 'WARN', '자동 실패 → data/nlic_raw/ 에 Excel 수동 저장 후 --combine-nlic 실행')


def run_monthly() -> None:
    run_weekly()   # 주간 포함
    print('\n[물동량] 부산항 NLIC 갱신...')
    _update_throughput()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    parser = argparse.ArgumentParser(description='위밋모빌리티 데이터 자동 갱신')
    parser.add_argument('--mode', choices=['daily', 'weekly', 'monthly'],
                        default='daily', help='갱신 주기 모드')
    parser.add_argument('--combine-freight', action='store_true',
                        help='운임지수 XLS 합치기만 실행')
    parser.add_argument('--combine-nlic', action='store_true',
                        help='NLIC 물동량 XLS 합치기만 실행')
    args = parser.parse_args()

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print('=' * 58)
    print(f'  위밋모빌리티 데이터 갱신  [{now}]')

    if args.combine_freight:
        print('  모드: 운임지수 XLS 합치기')
        print('=' * 58)
        from src.freight_index_loader import combine_freight_excels
        combine_freight_excels(FREIGHT_DIR, DATA_DIR / 'kcci_weekly.csv')
        return

    if args.combine_nlic:
        print('  모드: NLIC 물동량 합치기')
        print('=' * 58)
        from src.nlic_fetcher import combine_nlic_excels
        combine_nlic_excels(NLIC_DIR, DATA_DIR / 'busan_throughput.csv')
        return

    print(f'  모드: {args.mode.upper()}')
    print('=' * 58)

    if   args.mode == 'daily':   run_daily()
    elif args.mode == 'weekly':  run_weekly()
    elif args.mode == 'monthly': run_monthly()

    # 결과 요약
    if _results:
        ok   = sum(1 for r in _results.values() if r['status'] == 'OK')
        warn = sum(1 for r in _results.values() if r['status'] == 'WARN')
        fail = sum(1 for r in _results.values() if r['status'] == 'FAIL')
        print(f'\n  결과: 성공 {ok}  경고 {warn}  실패 {fail}')

        log_fp = LOG_DIR / f'update_{args.mode}_{datetime.today().strftime("%Y%m%d")}.json'
        log_fp.write_text(
            json.dumps({'run_at': now, 'mode': args.mode, 'results': _results},
                       ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    print('=' * 58)


if __name__ == '__main__':
    main()
