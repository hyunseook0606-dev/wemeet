"""
monthly_update.py — 월별 데이터 자동 갱신 스크립트
실행: python scripts/monthly_update.py

[자동 갱신 대상]
  자동 (키 불필요):
    - 해사 뉴스 RSS (gCaptain / Splash247 / 한국해운신문)
    - USD/KRW 환율 (frankfurter.app → ECOS)
    - Brent 유가 (FRED 미국 연방준비제도)

  API 키 필요 (환경변수 설정 시 자동):
    - 환율 공식값 (ECOS_API_KEY)
    - 두바이유 공식값 (ECOS_API_KEY)
    - KCCI 운임지수 (DATA_GO_KR_KEY)

  자동 불가 (수동 대체):
    - 부산항 물동량 (NLIC Excel): 자동 다운로드 시도 → 실패 시 안내 출력
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('monthly_update')

DATA_DIR  = ROOT / 'data'
CACHE_DIR = ROOT / 'data' / 'ecos_cache'
NLIC_DIR  = ROOT / 'data' / 'nlic_raw'
LOG_DIR   = ROOT / 'data' / 'update_logs'

for d in [DATA_DIR, CACHE_DIR, NLIC_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── 결과 저장 ──────────────────────────────────────────────

_results: dict[str, dict] = {}

def _record(name: str, status: str, detail: str = '') -> None:
    _results[name] = {'status': status, 'detail': detail,
                      'time': datetime.now().strftime('%H:%M:%S')}
    icon = '✅' if status == 'OK' else ('⚠️' if status == 'WARN' else '❌')
    print(f'  {icon} {name}: {detail}')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 해사 뉴스 RSS (자동)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_news() -> None:
    print('\n[1] 해사 뉴스 RSS 수집...')
    try:
        from src.real_data_fetcher import fetch_maritime_news
        df = fetch_maritime_news(max_per_source=20, days_back=35)
        if not df.empty:
            _record('해사뉴스', 'OK', f'{len(df)}건 수집')
        else:
            _record('해사뉴스', 'WARN', '수집 결과 없음')
    except Exception as e:
        _record('해사뉴스', 'FAIL', str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 환율 (ECOS → frankfurter 폴백)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_exchange_rate() -> None:
    print('\n[2] USD/KRW 환율 갱신...')
    from src.real_data_fetcher import fetch_ecos_exchange_rate, fetch_exchange_rate_monthly

    # ECOS 캐시 삭제 후 재수집 (최신 데이터 확보)
    for f in CACHE_DIR.glob('731Y*'):
        f.unlink()
        logger.info('ECOS 캐시 삭제: %s', f.name)
    for f in CACHE_DIR.glob('021Y*'):
        f.unlink()

    start_ym = '202001'
    df = fetch_ecos_exchange_rate(start_ym, cache_dir=CACHE_DIR)
    if df is not None:
        _record('환율', 'OK', f'ECOS: {len(df)}개월 ({df["date"].min().strftime("%Y.%m")}~{df["date"].max().strftime("%Y.%m")})')
        return

    df = fetch_exchange_rate_monthly(start='2020-01-01')
    if df is not None:
        _record('환율', 'OK', f'frankfurter.app: {len(df)}개월')
    else:
        _record('환율', 'FAIL', 'ECOS + frankfurter 모두 실패')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 유가 (ECOS → FRED 폴백)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_oil_price() -> None:
    print('\n[3] 원유 유가 갱신...')
    from src.real_data_fetcher import fetch_ecos_oil_price, fetch_brent_oil_monthly

    for f in CACHE_DIR.glob('902Y*'):
        f.unlink()

    df = fetch_ecos_oil_price('202001', cache_dir=CACHE_DIR)
    if df is not None:
        _record('유가', 'OK', f'ECOS 두바이유: {len(df)}개월')
        return

    df = fetch_brent_oil_monthly(start='2020-01-01')
    if df is not None:
        _record('유가', 'OK', f'FRED Brent: {len(df)}개월')
    else:
        _record('유가', 'FAIL', 'ECOS + FRED 모두 실패')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 부산항 물동량 (NLIC 자동 다운로드 시도)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_throughput() -> None:
    print('\n[4] 부산항 물동량 갱신 (NLIC)...')
    from src.nlic_fetcher import download_nlic_range, combine_nlic_excels

    today   = datetime.today()
    # 이번 달 ~ 2개월 전 시도 (NLIC는 최신 데이터 1~2개월 지연 가능)
    prev2_y = today.year if today.month > 2 else today.year - 1
    prev2_m = (today.month - 2) % 12 or 12
    start_ym = f'{prev2_y}{prev2_m:02d}'
    end_ym   = today.strftime('%Y%m')

    fps = download_nlic_range(start_ym, end_ym, save_dir=NLIC_DIR)

    if fps:
        out_csv = DATA_DIR / 'busan_throughput.csv'
        df = combine_nlic_excels(NLIC_DIR, out_csv)
        if df is not None:
            _record('부산항물동량', 'OK',
                    f'NLIC 자동: {len(df)}개월 (최신: {df["date"].max().strftime("%Y.%m")})')
            return

    # 자동 실패 → 안내 출력
    _record('부산항물동량', 'WARN',
            '자동 다운로드 실패 → 수동 다운로드 필요 (아래 안내 참조)')
    print()
    print('  ┌─ 수동 다운로드 안내 ───────────────────────────────────────')
    print('  │  1. https://nlic.go.kr/nlic/seaHarborGtqy.action 접속')
    print('  │  2. 항만명: 부산 / 기간: 최신 달 선택')
    print('  │  3. Excel 다운로드 → data/nlic_raw/ 폴더에 저장')
    print('  │  4. python scripts/monthly_update.py --combine-only 실행')
    print('  └──────────────────────────────────────────────────────────')


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. KCCI 운임지수 (API 키 있을 때만)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_kcci() -> None:
    print('\n[5] KCCI 운임지수 갱신...')
    if not os.environ.get('DATA_GO_KR_KEY'):
        _record('KCCI', 'WARN', 'DATA_GO_KR_KEY 미설정 → 건너뜀')
        print('     발급: https://www.data.go.kr/data/15131881/openapi.do')
        return
    try:
        from src.real_data_fetcher import fetch_kcci_api
        df = fetch_kcci_api()
        if df is not None:
            out = DATA_DIR / 'kcci.csv'
            df.to_csv(out, index=False, encoding='utf-8-sig')
            _record('KCCI', 'OK', f'{len(df)}건 → {out.name}')
        else:
            _record('KCCI', 'FAIL', 'API 응답 없음')
    except Exception as e:
        _record('KCCI', 'FAIL', str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main(combine_only: bool = False) -> None:
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print('=' * 60)
    print(f'  위밋모빌리티 데이터 월별 자동 갱신')
    print(f'  실행 시각: {now}')
    print('=' * 60)

    if combine_only:
        # Excel 합치기만 실행 (수동 다운로드 후 사용)
        print('\n[NLIC Excel 합치기 모드]')
        from src.nlic_fetcher import combine_nlic_excels
        out_csv = DATA_DIR / 'busan_throughput.csv'
        df = combine_nlic_excels(NLIC_DIR, out_csv)
        if df is None:
            print('\n⚠️  합칠 파일이 없습니다. data/nlic_raw/ 폴더에 Excel 파일을 저장하세요.')
        return

    # 전체 갱신
    update_news()
    update_exchange_rate()
    update_oil_price()
    update_throughput()
    update_kcci()

    # 결과 요약
    print('\n' + '=' * 60)
    print('  갱신 결과 요약')
    print('=' * 60)
    ok   = sum(1 for r in _results.values() if r['status'] == 'OK')
    warn = sum(1 for r in _results.values() if r['status'] == 'WARN')
    fail = sum(1 for r in _results.values() if r['status'] == 'FAIL')
    print(f'  성공: {ok}  경고: {warn}  실패: {fail}')

    # 결과 로그 저장
    log_fp = LOG_DIR / f'update_{datetime.today().strftime("%Y%m")}.json'
    with open(log_fp, 'w', encoding='utf-8') as f:
        json.dump({'run_at': now, 'results': _results}, f,
                  ensure_ascii=False, indent=2)
    print(f'  로그 저장: {log_fp.name}')
    print('=' * 60)


if __name__ == '__main__':
    combine_only = '--combine-only' in sys.argv
    main(combine_only=combine_only)
