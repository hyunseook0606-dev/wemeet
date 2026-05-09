"""카카오 API 실데이터 end-to-end 테스트."""
import sys, os
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv('.env', override=True)

from src.odcy_recommender import recommend_storage, CargoType
from src.option_presenter  import generate_four_options, format_option_table

kakao_key = os.getenv('KAKAO_REST_API_KEY', '')
mobi_key  = os.getenv('KAKAO_MOBILITY_KEY', '')

print(f'카카오 Local  : {"OK (실데이터)" if kakao_key else "없음 (시뮬)"}')
print(f'카카오 모빌리티: {"OK (실데이터)" if mobi_key else "없음 (Haversine)"}')

# --- 일반화물 ---
print('\n=== 일반화물 / 부산항 북항 ===')
r1 = recommend_storage('부산항(북항)', CargoType.GENERAL, top_n=3,
                       kakao_rest_key=kakao_key, kakao_mobility_key=mobi_key)
print(f'모드: {"실데이터(카카오)" if not r1["simulation_mode"] else "시뮬레이션 DB"}')
for mode in ['distance', 'time', 'comprehensive']:
    items = r1['recommendations'][mode]
    if items:
        w = items[0]
        src = w.get('route_source', '')
        print(f'  [{mode:13s}] {w["name"][:25]} | {w["distance_km"]}km | {w["duration_min"]}분 | [{src}]')

# --- 4가지 옵션 ---
print('\n=== 4가지 대응 옵션 비교 ===')
options = generate_four_options(
    {'cargo_type': '일반화물', 'cbm': 20.0, 'region': '경기남부'},
    r1, delay_days=14, freight_usd=900
)
print(format_option_table(options))

# --- 냉장화물 ---
print('\n=== 냉장화물 / 부산 신항 ===')
r2 = recommend_storage('부산 신항', CargoType.REFRIGERATED, top_n=3,
                       kakao_rest_key=kakao_key, kakao_mobility_key=mobi_key)
print(f'모드: {"실데이터(카카오)" if not r2["simulation_mode"] else "시뮬레이션 DB"}')
for w in r2['recommendations']['comprehensive'][:3]:
    src = w.get('route_source', '')
    print(f'  {w["name"][:30]} | {w["distance_km"]}km | {w["duration_min"]}분 | [{src}]')
