import { useEffect, useRef, useState } from 'react'

const KAKAO_JS_KEY = import.meta.env.VITE_KAKAO_JS_KEY

// 부산 중심 좌표 (기본)
const BUSAN_CENTER = { lat: 35.1796, lng: 129.0756 }

// 창고 마커 색상: 보세(파랑), 냉장(하늘), 일반(초록), ODCY(주황)
const MARKER_COLORS = {
  bonded: '#2563EB',
  cold: '#06B6D4',
  general: '#22C55E',
  odcy: '#F97316',
}

function getMarkerColor(w) {
  if (w.bonded) return MARKER_COLORS.bonded
  if (w.cold_chain) return MARKER_COLORS.cold
  return MARKER_COLORS.general
}

function loadKakaoScript(key) {
  return new Promise((resolve, reject) => {
    // 완전히 초기화된 경우 (LatLng 존재 확인)
    if (window.kakao?.maps?.LatLng) { resolve(window.kakao.maps); return }

    // SDK 객체는 있지만 아직 초기화 중인 경우 → load() 콜백으로 대기
    if (window.kakao?.maps) {
      window.kakao.maps.load(() => resolve(window.kakao.maps))
      return
    }

    const existing = document.getElementById('kakao-maps-sdk')
    if (existing) {
      const wait = () => {
        if (window.kakao?.maps) window.kakao.maps.load(() => resolve(window.kakao.maps))
        else setTimeout(wait, 100)
      }
      wait()
      return
    }

    const script = document.createElement('script')
    script.id = 'kakao-maps-sdk'
    script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${key}&libraries=services&autoload=false`
    script.onload = () => window.kakao.maps.load(() => resolve(window.kakao.maps))
    script.onerror = reject
    document.head.appendChild(script)
  })
}

export default function KakaoMap({ warehouses = [], selectedIndex = 0, onSelect }) {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const markersRef = useRef([])
  const [mapLoaded, setMapLoaded] = useState(false)
  const [mapError, setMapError] = useState(false)

  // 지도 초기화
  useEffect(() => {
    if (!KAKAO_JS_KEY || KAKAO_JS_KEY === 'undefined') {
      console.error('[KakaoMap] VITE_KAKAO_JS_KEY 미설정:', KAKAO_JS_KEY)
      setMapError('key')
      return
    }

    console.log('[KakaoMap] JS Key 확인:', KAKAO_JS_KEY.slice(0, 8) + '...')
    loadKakaoScript(KAKAO_JS_KEY)
      .then((maps) => {
        if (!mapRef.current || mapInstance.current) return
        const container = mapRef.current
        const options = {
          center: new maps.LatLng(BUSAN_CENTER.lat, BUSAN_CENTER.lng),
          level: 8,
        }
        mapInstance.current = new maps.Map(container, options)
        setMapLoaded(true)
      })
      .catch((e) => { console.error('[KakaoMap] SDK 로드 실패:', e); setMapError('sdk') })
  }, [])

  // 창고 마커 렌더링
  useEffect(() => {
    if (!mapLoaded || !mapInstance.current || warehouses.length === 0) return
    const maps = window.kakao.maps

    // 기존 마커 제거
    markersRef.current.forEach((m) => m.setMap(null))
    markersRef.current = []

    const bounds = new maps.LatLngBounds()

    const placeMarker = (w, i, coords) => {
      bounds.extend(coords)
      const isSelected = i === selectedIndex
      const color = getMarkerColor(w)

      const svgContent = `
        <svg xmlns="http://www.w3.org/2000/svg" width="${isSelected ? 40 : 32}" height="${isSelected ? 50 : 40}" viewBox="0 0 40 50">
          <ellipse cx="20" cy="48" rx="8" ry="3" fill="rgba(0,0,0,0.3)"/>
          <path d="M20 0C12.3 0 6 6.3 6 14c0 10.5 14 34 14 34s14-23.5 14-34C34 6.3 27.7 0 20 0z" fill="${color}" stroke="white" stroke-width="2"/>
          <circle cx="20" cy="14" r="6" fill="white"/>
          <text x="20" y="18" text-anchor="middle" font-size="10" font-weight="bold" fill="${color}">${i + 1}</text>
        </svg>`

      const markerImage = new maps.MarkerImage(
        `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svgContent)))}`,
        new maps.Size(isSelected ? 40 : 32, isSelected ? 50 : 40)
      )

      const marker = new maps.Marker({
        position: coords,
        map: mapInstance.current,
        image: markerImage,
        title: w.name,
      })

      const infoContent = `
        <div style="padding:10px 12px;min-width:180px;font-family:sans-serif;font-size:13px;border-radius:8px">
          <strong style="color:#1e293b">${w.name}</strong><br/>
          <span style="color:#64748b;font-size:11px">${w.address}</span><br/>
          ${w.distance_km ? `<span style="color:#2563EB;font-size:11px">📍 ${w.distance_km}km · ${w.duration_min}분</span>` : ''}
        </div>`

      const infoWindow = new maps.InfoWindow({ content: infoContent, removable: true })
      maps.event.addListener(marker, 'click', () => {
        infoWindow.open(mapInstance.current, marker)
        onSelect?.(i)
      })
      if (isSelected) infoWindow.open(mapInstance.current, marker)
      markersRef.current.push(marker)

      if (markersRef.current.length === warehouses.length) {
        mapInstance.current.setBounds(bounds)
      }
    }

    const geocoder = new maps.services.Geocoder()
    warehouses.forEach((w, i) => {
      // lat/lng 있으면 직접 사용, 없으면 주소 geocoding fallback
      if (w.lat && w.lng) {
        const coords = new maps.LatLng(w.lat, w.lng)
        placeMarker(w, i, coords)
      } else if (w.address) {
        geocoder.addressSearch(w.address, (result, status) => {
          if (status !== maps.services.Status.OK) return
          const coords = new maps.LatLng(result[0].y, result[0].x)
          placeMarker(w, i, coords)
        })
      }
    })
  }, [mapLoaded, warehouses, selectedIndex, onSelect])

  if (mapError || !KAKAO_JS_KEY) {
    const errMsg = mapError === 'key'
      ? 'VITE_KAKAO_JS_KEY 환경변수 미설정'
      : mapError === 'sdk'
      ? 'Kakao SDK 로드 실패 — 도메인(localhost:3000) 등록 확인'
      : 'VITE_KAKAO_JS_KEY 설정을 확인해주세요.'
    return (
      <div className="w-full h-full rounded-xl bg-[#0D1627] border border-white/10 flex flex-col items-center justify-center gap-3 p-6">
        <div className="text-4xl">🗺️</div>
        <p className="text-slate-400 text-sm text-center">
          카카오맵을 불러올 수 없습니다.<br/>
          <span className="text-slate-600 text-xs">{errMsg}</span>
        </p>
        {/* 창고 목록 텍스트 표시 */}
        <div className="w-full mt-2 space-y-2">
          {warehouses.map((w, i) => (
            <button
              key={i}
              onClick={() => onSelect?.(i)}
              className={`w-full text-left p-3 rounded-lg text-sm transition-all ${
                i === selectedIndex
                  ? 'bg-blue-600/20 border border-blue-500/40 text-white'
                  : 'bg-white/5 border border-transparent text-slate-400 hover:text-white'
              }`}
            >
              <span className="font-medium">{w.name}</span>
              <span className="text-xs ml-2 text-slate-500">{w.address}</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden">
      <div ref={mapRef} className="w-full h-full" />
      {!mapLoaded && (
        <div className="absolute inset-0 bg-[#0D1627] flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
        </div>
      )}
      {/* 범례 */}
      <div className="absolute bottom-3 left-3 bg-[#0A0F1E]/90 backdrop-blur rounded-lg p-2 text-xs space-y-1">
        {Object.entries({ '보세창고': MARKER_COLORS.bonded, '냉장창고': MARKER_COLORS.cold, '일반창고': MARKER_COLORS.general }).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1.5 text-slate-400">
            <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: color }} />
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}
