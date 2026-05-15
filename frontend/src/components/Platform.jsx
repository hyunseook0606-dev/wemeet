import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../hooks/useApi'
import KakaoMap from './KakaoMap'

const ROUTES = [
  { id: '부산→로테르담', transit_days: 28, usd_per_teu: 3500 },
  { id: '부산→LA', transit_days: 14, usd_per_teu: 2300 },
  { id: '부산→상하이', transit_days: 3, usd_per_teu: 950 },
  { id: '부산→싱가포르', transit_days: 7, usd_per_teu: 1050 },
  { id: '부산→도쿄', transit_days: 2, usd_per_teu: 680 },
]
const CARGO_TYPES = ['냉장화물', '일반화물', '위험물', '자동차부품', '2차전지', '의류/섬유', '전자제품']
const PORT_NAMES = ['부산항(북항)', '부산 신항', '인천항', '평택항', '광양항', '울산항']

const OPTION_COLORS = { A: '#EF4444', B: '#F97316', C: '#3B82F6', D: '#22C55E' }

function StatusBadge({ status, elapsed }) {
  const map = {
    waking:  { label: elapsed > 0 ? `기동 중 ${elapsed}s…` : '기동 중…', color: '#F97316', pulse: true },
    online:  { label: '연결됨',  color: '#22C55E', pulse: true },
    offline: { label: '재시도 중', color: '#EF4444', pulse: true },
  }
  const s = map[status] || map.waking
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${s.pulse ? 'animate-pulse' : ''}`} style={{ background: s.color }} />
      <span className="text-xs" style={{ color: s.color }}>{s.label}</span>
    </div>
  )
}

// Step 1: 화주 정보 입력 폼
function ShipmentForm({ onResult, apiStatus, elapsed }) {
  const [form, setForm] = useState({
    company: '(주)테스트기업',
    cargo_type: '냉장화물',
    cbm: 15,
    route: '부산→로테르담',
    pickup_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
    deadline_days: 14,
    region: '국내수도권',
    urgent: false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const routeMap = {
    '부산→로테르담': '부산→로테르담',
    '부산→LA': '부산→LA',
    '부산→상하이': '부산→상하이',
    '부산→싱가포르': '부산→싱가포르',
    '부산→도쿄': '부산→도쿄',
  }

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await api.post('/shipment/register', {
        ...form,
        cbm: parseFloat(form.cbm),
        deadline_days: parseInt(form.deadline_days),
        route: routeMap[form.route] || form.route,
      })
      onResult(res.data, { ...form, cbm: parseFloat(form.cbm) })
    } catch (err) {
      const msg = err.code === 'ECONNABORTED' || err.message?.includes('timeout')
        ? '서버 응답 대기 중 타임아웃 — Render 서버가 기동 중입니다. 30초 후 다시 시도해주세요.'
        : (err.response?.data?.detail || err.message || '요청 실패')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const field = (label, children) => (
    <div className="flex flex-col gap-1">
      <label className="text-slate-400 text-xs font-medium">{label}</label>
      {children}
    </div>
  )

  const inputCls = "bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500/50 transition-colors"

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-white font-semibold">Step 1 · 화주 정보 입력</h3>
        <StatusBadge status={apiStatus} elapsed={elapsed} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        {field('회사명',
          <input className={inputCls} value={form.company}
            onChange={e => setForm(p => ({...p, company: e.target.value}))} />
        )}
        {field('화물 종류',
          <select className={inputCls} value={form.cargo_type}
            onChange={e => setForm(p => ({...p, cargo_type: e.target.value}))}>
            {CARGO_TYPES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
        {field('CBM (부피)',
          <input type="number" className={inputCls} value={form.cbm} min="1" max="35" step="0.5"
            onChange={e => setForm(p => ({...p, cbm: e.target.value}))} />
        )}
        {field('항로',
          <select className={inputCls} value={form.route}
            onChange={e => setForm(p => ({...p, route: e.target.value}))}>
            {ROUTES.map(r => <option key={r.id} value={r.id}>{r.id} ({r.transit_days}일)</option>)}
          </select>
        )}
        {field('출발 예정일',
          <input type="date" className={inputCls} value={form.pickup_date}
            onChange={e => setForm(p => ({...p, pickup_date: e.target.value}))} />
        )}
        {field('납기일 (일)',
          <select className={inputCls} value={form.deadline_days}
            onChange={e => setForm(p => ({...p, deadline_days: parseInt(e.target.value)}))}>
            {[7,10,14,21].map(d => <option key={d} value={d}>{d}일</option>)}
          </select>
        )}
      </div>

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 cursor-pointer text-slate-400 text-sm">
          <input type="checkbox" className="w-4 h-4 accent-blue-500"
            checked={form.urgent} onChange={e => setForm(p => ({...p, urgent: e.target.checked}))} />
          긴급 화물
        </label>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
          {typeof error === 'object' ? JSON.stringify(error) : error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold text-sm
          hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            MRI 분석 중...
          </>
        ) : (
          'AI 리스크 분석 시작 →'
        )}
      </button>

      {apiStatus === 'offline' && (
        <p className="text-center text-slate-500 text-xs">
          연결 확인 중… 잠시 후 자동 재시도합니다
        </p>
      )}
    </form>
  )
}

// Step 2: 분석 결과 + 유사사례 + LSTM + 창고 추천 요청
function AnalysisResult({ shipmentResult, onWarehouseResult, portName, setPortName }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [similarEvents, setSimilarEvents] = useState(null)
  const [lstmForecast, setLstmForecast] = useState(null)

  const mri = shipmentResult.mri ?? 0
  const gradeColor = mri >= 0.7 ? '#EF4444' : mri >= 0.5 ? '#F97316' : mri >= 0.3 ? '#EAB308' : '#22C55E'

  useEffect(() => {
    api.get('/mri/similar-events').then(r => setSimilarEvents(r.data)).catch(() => {})
    api.get('/mri/lstm-forecast').then(r => setLstmForecast(r.data)).catch(() => {})
  }, [])

  const requestWarehouse = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.post('/warehouse/recommend', {
        port_name: portName,
        cargo_type: shipmentResult?.cargo_type || '일반화물',
        cbm: shipmentResult?.cbm || 15,
        mri_score: shipmentResult.mri,
        delay_days: shipmentResult.estimated_delay_days || 14,
        freight_usd: shipmentResult.estimated_cost,
        region: shipmentResult?.region || formData?.region || '경기남부',
      }, { timeout: 120000 })
      onWarehouseResult(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-white font-semibold">Step 2 · 분석 결과</h3>

      {/* MRI + 등급 */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
          <div className="text-3xl font-bold text-gradient">{(shipmentResult.mri * 100).toFixed(0)}</div>
          <div className="text-slate-500 text-xs mt-1">MRI 지수</div>
        </div>
        <div className="rounded-xl p-4 text-center" style={{
          background: `${gradeColor}15`, border: `1px solid ${gradeColor}40`
        }}>
          <div className="text-white text-sm font-bold" style={{ color: gradeColor }}>
            {shipmentResult.grade ?? '—'}
          </div>
          <div className="text-slate-400 text-xs mt-1">리스크 등급</div>
        </div>
      </div>

      {/* 현재 이슈 + 뉴스 키워드 */}
      {(shipmentResult.current_issue || (shipmentResult.top_keywords?.length ?? 0) > 0) && (
        <div className="space-y-2">
          {shipmentResult.current_issue && (
            <div className="text-slate-300 text-xs bg-white/5 rounded-lg px-3 py-2">
              📡 {shipmentResult.current_issue}
            </div>
          )}
          {(shipmentResult.top_keywords?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {shipmentResult.top_keywords.slice(0, 5).map((kw, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background: 'rgba(59,130,246,0.15)',
                    color: '#93C5FD',
                    border: '1px solid rgba(59,130,246,0.3)',
                  }}
                >
                  #{kw}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 영향 분석 */}
      <div className="space-y-2">
        {[
          { label: '예상 비용', value: `$${shipmentResult.estimated_cost?.toLocaleString()}`, delta: (shipmentResult.estimated_cost_delta ?? shipmentResult.cost_delta) > 0 ? `+$${shipmentResult.estimated_cost_delta ?? shipmentResult.cost_delta}` : null },
          { label: '지연 일수', value: `${shipmentResult.estimated_delay_days ?? shipmentResult.delay_days ?? 0}일`, warn: (shipmentResult.estimated_delay_days ?? shipmentResult.delay_days ?? 0) > 0 },
          { label: '수정 출발일', value: shipmentResult.new_pickup_date },
          { label: '납기 위반', value: (shipmentResult.deadline_at_risk ?? shipmentResult.deadline_violated) ? '위반' : '정상', warn: (shipmentResult.deadline_at_risk ?? shipmentResult.deadline_violated) },
        ].map(item => (
          <div key={item.label} className="flex justify-between text-sm py-1.5 border-b border-white/5">
            <span className="text-slate-500">{item.label}</span>
            <span className={`font-medium ${item.warn ? 'text-red-400' : 'text-white'}`}>
              {item.value}
              {item.delta && <span className="text-red-400 text-xs ml-1">{item.delta}</span>}
            </span>
          </div>
        ))}
      </div>

      <p className="text-slate-500 text-xs bg-white/5 rounded-lg p-3">{shipmentResult.advisory_note || shipmentResult.current_issue || shipmentResult.reason}</p>

      {/* 과거 유사사례 */}
      {similarEvents && similarEvents.events?.length > 0 && (
        <div className="bg-white/5 border border-white/8 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-white text-xs font-semibold">📌 과거 유사사례 (참고)</span>
            <div className="flex gap-3 text-xs">
              <span className="text-slate-400">평균 지연 <span className="text-amber-400 font-bold">+{similarEvents.avg_delay}일</span></span>
              <span className="text-slate-400">운임 <span className="text-red-400 font-bold">+{similarEvents.avg_freight}%</span></span>
            </div>
          </div>
          <div className="space-y-1">
            {similarEvents.events.slice(0, 3).map((ev, i) => (
              <div key={i} className="text-xs text-slate-500 flex justify-between py-0.5 border-b border-white/5">
                <span className="text-slate-400">{ev.name}</span>
                <span>지연 {ev.avg_delay_days}일 · 운임 +{ev.avg_freight_increase_pct}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 부산항 물동량 LSTM 예측 */}
      {lstmForecast && lstmForecast.forecast?.length > 0 && (
        <div className="bg-white/5 border border-white/8 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-white text-xs font-semibold">📈 부산항 물동량 예측 (LSTM)</span>
            {lstmForecast.mape > 0 && (
              <span className="text-slate-500 text-xs">MAPE {lstmForecast.mape}%</span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {lstmForecast.forecast.map((f, i) => (
              <div key={i} className="text-center bg-white/5 rounded-lg py-2">
                <div className="text-blue-300 text-xs font-bold">{f.month}</div>
                <div className="text-white text-sm font-semibold">{f.teu_10k}만 TEU</div>
              </div>
            ))}
          </div>
          <p className="text-slate-600 text-xs">기준: 부산항 평년 200만 TEU/월</p>
        </div>
      )}

      {/* 창고 추천 — MRI 등급 무관하게 모든 화주에게 제공 */}
      <div className="flex flex-col gap-2">
        <label className="text-slate-400 text-xs font-medium">출발 항구</label>
        <select
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500/50"
          value={portName} onChange={e => setPortName(e.target.value)}
        >
          {PORT_NAMES.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      {error && <p className="text-red-400 text-xs">{error}</p>}
      <button
        onClick={requestWarehouse}
        disabled={loading}
        className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {loading ? (
          <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />창고 탐색 중...</>
        ) : '📦 창고 추천 + 비용 비교 보기 →'}
      </button>
    </div>
  )
}

// 공동물류 그룹 편성 패널
// 팀원 원본 reorganizer.py 로직 기반:
//   - 권역·화물 호환·날짜 ±2일 조건으로 자동 그룹 편성
//   - CONSOLIDATION_SAVINGS_RATE = 0.15 (15% 절감)
//   - CARGO_COMPAT: 동일 화물 유형끼리만 묶음
function JointLogisticsPanel({ shipmentResult }) {
  const [grouped, setGrouped] = useState(false)
  const myCbm = shipmentResult?.cbm || 15
  const cargoType = shipmentResult?.cargo_type || '일반화물'

  const mockPeers = [
    { company: '(주)한강식품', cbm: 12, region: '경기남부', cargo: cargoType },
    { company: '대성무역(주)',  cbm: 8,  region: '충청',     cargo: cargoType },
  ]

  const totalCbm     = myCbm + mockPeers.reduce((s, p) => s + p.cbm, 0)
  const containerCap = 33
  const fillPct      = Math.min(Math.round((totalCbm / containerCap) * 100), 100)

  // 팀원 원본 config.py: CONSOLIDATION_SAVINGS_RATE = 0.15
  const SAVINGS_RATE = 0.15
  const baseCost     = shipmentResult?.estimated_cost || 2000
  const myLcl        = Math.round(baseCost * (1 - SAVINGS_RATE))
  const saving       = Math.round(baseCost * SAVINGS_RATE)

  return (
    <div className="bg-emerald-900/10 border border-emerald-500/25 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-emerald-400 font-semibold text-sm">🚢 공동물류 그룹 편성</span>
        <span className="text-xs text-slate-500">동일 권역 · 동일 화물 유형 자동 매칭</span>
      </div>

      {/* 참여 화주 목록 */}
      <div className="space-y-1.5">
        {/* 내 화물 */}
        <div className="flex items-center justify-between bg-blue-600/15 border border-blue-500/30 rounded-lg px-3 py-2 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            <span className="text-white font-medium">{shipmentResult?.company || '내 화물'}</span>
            <span className="text-slate-400">({cargoType})</span>
          </div>
          <span className="text-blue-300 font-bold">{myCbm} CBM</span>
        </div>
        {/* 매칭된 화주들 */}
        {mockPeers.map((p, i) => (
          <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-slate-300">{p.company}</span>
              <span className="text-slate-500">({p.region})</span>
            </div>
            <span className="text-emerald-300 font-bold">{p.cbm} CBM</span>
          </div>
        ))}
      </div>

      {/* 컨테이너 적재율 바 */}
      <div>
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>컨테이너 적재율</span>
          <span className="text-white font-medium">{totalCbm} / {containerCap} CBM ({fillPct}%)</span>
        </div>
        <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000"
            style={{
              width: `${fillPct}%`,
              background: 'linear-gradient(to right, #10B981, #06B6D4)',
            }}
          />
        </div>
      </div>

      {/* 비용 비교 — CONSOLIDATION_SAVINGS_RATE 15% 적용 */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="bg-white/5 rounded-lg py-2">
          <div className="text-slate-400">개별 운송</div>
          <div className="text-red-400 font-bold mt-0.5">${baseCost.toLocaleString()}</div>
        </div>
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg py-2">
          <div className="text-emerald-300">LCL 공동</div>
          <div className="text-emerald-300 font-bold mt-0.5">${myLcl.toLocaleString()}</div>
        </div>
        <div className="bg-white/5 rounded-lg py-2">
          <div className="text-slate-400">절감 (15%)</div>
          <div className="text-emerald-400 font-bold mt-0.5">-${saving.toLocaleString()}</div>
        </div>
      </div>

      <div className="text-center">
        {!grouped ? (
          <button
            onClick={() => setGrouped(true)}
            className="w-full py-2 rounded-lg bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 text-xs font-medium hover:bg-emerald-600/50 transition-all"
          >
            LCL 공동 그룹 확정 →
          </button>
        ) : (
          <div className="py-2 rounded-lg bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 text-xs font-medium">
            ✅ 그룹 편성 완료 — Routy 배차에 반영됩니다
          </div>
        )}
      </div>
    </div>
  )
}

// Step 3: 창고 + 지도 + A/B/C 시나리오 비용 비교
function WarehouseResult({ warehouseData, shipmentResult }) {
  const [selectedWH, setSelectedWH] = useState(0)
  const [selectedOption, setSelectedOption] = useState('C')

  const warehouses = warehouseData.warehouses || []
  // API가 반환하는 scenarios (label/name/storage_krw/transfer_krw/total_krw/recommend)
  const scenarios = warehouseData.scenarios || []

  return (
    <div className="space-y-5">
      <h3 className="text-white font-semibold">Step 3 · 창고 추천 + A/B/C 시나리오</h3>

      {/* 카카오맵 */}
      <div style={{ height: '280px' }}>
        <KakaoMap
          warehouses={warehouses}
          selectedIndex={selectedWH}
          onSelect={setSelectedWH}
        />
      </div>

      {/* 창고 목록 */}
      <div className="space-y-2">
        {warehouses.map((w, i) => (
          <button
            key={i}
            onClick={() => setSelectedWH(i)}
            className={`w-full text-left p-3 rounded-xl border transition-all text-sm ${
              i === selectedWH
                ? 'bg-blue-600/15 border-blue-500/40 text-white'
                : 'bg-white/5 border-transparent text-slate-400 hover:text-white hover:border-white/10'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium">{w.name}</span>
              <div className="flex gap-1 flex-wrap justify-end">
                {w.source === 'NLIC' && <span className="text-xs px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300">NLIC</span>}
                {w.bonded && <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300">보세</span>}
                {w.cold_chain && <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300">냉장</span>}
                {w.hazmat_license && <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">위험물</span>}
              </div>
            </div>
            <div className="text-slate-500 text-xs mt-0.5">{w.address}</div>
            <div className="flex flex-wrap gap-x-3 mt-1">
              {w.distance_km && (
                <span className="text-blue-400 text-xs">📍 {w.distance_km}km · {w.duration_min}분</span>
              )}
              {w.area_sqm && (
                <span className="text-slate-400 text-xs">📐 {w.area_sqm.toLocaleString()}㎡</span>
              )}
              {w.operating_hours && (
                <span className="text-slate-500 text-xs">🕐 {w.operating_hours}</span>
              )}
            </div>
            {w.cargo_types?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {w.cargo_types.map((ct, ci) => (
                  <span key={ci} className="text-xs px-1.5 py-0.5 rounded bg-white/5 text-slate-400">{ct}</span>
                ))}
              </div>
            )}
            {w.notes && (
              <div className="text-slate-600 text-xs mt-1 line-clamp-1">💬 {w.notes}</div>
            )}
          </button>
        ))}
      </div>

      {/* A/B/C 시나리오 비용 비교 */}
      {scenarios.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-white font-medium text-sm">A/B/C 시나리오 비용 비교</h4>
          <div className="grid grid-cols-3 gap-2">
            {scenarios.map((sc) => {
              const LABEL_COLORS = { A: '#F59E0B', B: '#EF4444', C: '#10B981' }
              const color = LABEL_COLORS[sc.label] || '#94A3B8'
              const isSelected = selectedOption === sc.label
              return (
                <button
                  key={sc.label}
                  onClick={() => setSelectedOption(sc.label)}
                  className="text-left p-3 rounded-xl border transition-all"
                  style={{
                    background: isSelected ? `${color}15` : 'rgba(255,255,255,0.03)',
                    borderColor: isSelected ? `${color}50` : 'rgba(255,255,255,0.08)',
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ background: color, color: '#fff' }}>
                      {sc.label}
                    </span>
                    {sc.recommend && (
                      <span className="text-xs text-green-400">★추천</span>
                    )}
                  </div>
                  <div className="text-white text-xs font-medium leading-tight">{sc.name}</div>
                  <div className="text-slate-300 text-xs mt-1 font-semibold">{sc.total_krw?.toLocaleString()}원</div>
                  <div className="text-slate-500 text-xs">보관 {sc.storage_krw?.toLocaleString()}원</div>
                </button>
              )
            })}
          </div>

          {/* 선택된 시나리오 상세 */}
          {(() => {
            const sc = scenarios.find(s => s.label === selectedOption)
            if (!sc) return null
            return (
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-xs space-y-2">
                <div className="font-semibold text-white">{sc.label}안 · {sc.name}</div>
                <div className="flex justify-between text-slate-400">
                  <span>보관료</span>
                  <span className="text-white">{sc.storage_krw?.toLocaleString()}원</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>이송비</span>
                  <span className="text-white">{sc.transfer_krw?.toLocaleString()}원</span>
                </div>
                <div className="border-t border-white/10 pt-2 flex justify-between font-bold text-white">
                  <span>합계</span>
                  <span className="text-green-400">{sc.total_krw?.toLocaleString()}원</span>
                </div>
                {sc.note && (
                  <div className="text-slate-500 text-xs pt-1">{sc.note}</div>
                )}
              </div>
            )
          })()}
        </div>
      )}

      {/* 공동물류 그룹 편성 */}
      <JointLogisticsPanel shipmentResult={shipmentResult} />
    </div>
  )
}

// Step 4: Routy JSON 생성
function RoutyPanel({ shipmentResult, warehouseResult, formData, portName }) {
  const [routyJson, setRoutyJson] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedWH, setSelectedWH] = useState(0)

  const warehouses = warehouseResult?.warehouses || []
  const wh = warehouses[selectedWH] || warehouses[0]

  const generate = async () => {
    if (!wh) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.post('/routy/generate', {
        shipment_id: shipmentResult.shipment_id,
        company: formData?.company || '(주)테스트기업',
        region: formData?.region || '경기남부',
        cargo_type: shipmentResult?.cargo_type || '일반화물',
        cbm: shipmentResult?.cbm || 15,
        origin_address: `${formData?.region || '경기'} 출발지`,
        port_name: portName,
        pickup_date: shipmentResult.new_pickup_date,
        mri_current: shipmentResult.mri,
        delay_reason: shipmentResult.current_issue || shipmentResult.advisory_note || '리스크 대응',
        warehouse_name: wh.name,
        warehouse_address: wh.address,
        warehouse_km: wh.distance_km || 0,
        warehouse_minutes: wh.duration_min || 0,
        warehouse_hours: wh.operating_hours || '',
        phase2_ready_date: null,
      })
      setRoutyJson(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const download = () => {
    if (!routyJson) return
    const blob = new Blob([JSON.stringify(routyJson, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `routy_${shipmentResult.shipment_id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card-glass rounded-2xl p-5 space-y-4">
      <h4 className="text-white font-medium text-sm">Step 4 · Routy JSON 생성</h4>

      {warehouses.length > 1 && (
        <div className="space-y-1">
          <p className="text-slate-400 text-xs">창고 선택</p>
          {warehouses.map((w, i) => (
            <button key={i} onClick={() => setSelectedWH(i)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-all ${
                i === selectedWH ? 'bg-blue-600/20 border border-blue-500/40 text-white' : 'bg-white/5 text-slate-400 hover:text-white'
              }`}>
              {w.name} · {w.distance_km}km
            </button>
          ))}
        </div>
      )}

      {error && <p className="text-red-400 text-xs">{error}</p>}

      {routyJson ? (
        <>
          <div className="bg-[#0D1627] rounded-xl p-4 text-xs font-mono text-green-400 overflow-auto max-h-52">
            {JSON.stringify(routyJson.phase1, null, 2)}
          </div>
          <button onClick={download}
            className="w-full py-3 rounded-xl border border-green-500/40 text-green-400 text-sm hover:bg-green-500/10 transition-all">
            📥 JSON 다운로드 (Phase 1 — 출발지→창고)
          </button>
        </>
      ) : (
        <button onClick={generate} disabled={loading || !wh}
          className="w-full py-3 rounded-xl border border-blue-500/40 text-blue-400 text-sm hover:bg-blue-500/10 transition-all disabled:opacity-50 flex items-center justify-center gap-2">
          {loading ? <><div className="w-4 h-4 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin" />생성 중...</> : '📄 Routy JSON 생성'}
        </button>
      )}
    </div>
  )
}

export default function Platform() {
  const [apiStatus, setApiStatus] = useState('waking')  // waking | online | offline
  const [elapsed, setElapsed] = useState(0)
  const [step, setStep] = useState(1)
  const [shipmentResult, setShipmentResult] = useState(null)
  const [warehouseResult, setWarehouseResult] = useState(null)
  const [formData, setFormData] = useState(null)
  const [portName, setPortName] = useState('부산항(북항)')

  // 마운트 시 서버 워밍업 (Render 무료 티어 콜드스타트 대응)
  useEffect(() => {
    let timerInterval
    setApiStatus('waking')
    setElapsed(0)
    timerInterval = setInterval(() => setElapsed(s => s + 1), 1000)

    api.get('/health', { timeout: 60000 })
      .then(() => { setApiStatus('online'); clearInterval(timerInterval) })
      .catch(() => { setApiStatus('offline'); clearInterval(timerInterval) })

    return () => clearInterval(timerInterval)
  }, [])

  const handleShipmentResult = (data, form) => {
    setShipmentResult(data)
    setFormData(form)
    if (data.departure_port) setPortName(data.departure_port)
    setStep(2)
  }

  const handleWarehouseResult = (data) => {
    setWarehouseResult(data)
    setStep(3)
  }

  const reset = () => { setStep(1); setShipmentResult(null); setWarehouseResult(null); setFormData(null) }

  return (
    <section className="py-24 bg-[#0A0F1E] relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(37,99,235,0.08) 0%, transparent 70%)' }} />
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/30 to-transparent" />

      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-14"
        >
          <span className="text-blue-400 text-sm font-medium tracking-widest uppercase">Live Platform Demo</span>
          <h2 className="text-4xl md:text-5xl font-bold text-white mt-3 mb-4">
            직접 체험해보는<br />
            <span className="text-gradient">AI 물류 플랫폼</span>
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            실제 백엔드 API와 연동된 플랫폼 데모입니다.
            화주 정보 입력 → MRI 분석 → 창고 추천 + 카카오맵까지 전 과정을 체험하세요.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-3 gap-4 mb-6">
          {[
            { n: 1, label: '화주 입력', icon: '📋' },
            { n: 2, label: '분석 결과', icon: '📊' },
            { n: 3, label: '창고 + 지도', icon: '🗺️' },
          ].map(s => (
            <div key={s.n} className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
              step === s.n ? 'bg-blue-600/15 border-blue-500/40' :
              step > s.n  ? 'bg-white/5 border-green-500/30' :
              'bg-white/3 border-white/5'
            }`}>
              <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                step > s.n ? 'bg-green-500/20 text-green-400' :
                step === s.n ? 'bg-blue-600 text-white' :
                'bg-white/10 text-slate-500'
              }`}>{step > s.n ? '✓' : s.n}</span>
              <span className={`text-sm font-medium ${step >= s.n ? 'text-white' : 'text-slate-500'}`}>
                {s.icon} {s.label}
              </span>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* 왼쪽: 폼/결과 패널 */}
          <div className="card-glass rounded-2xl p-6">
            <AnimatePresence mode="wait">
              {step === 1 && (
                <motion.div key="step1" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                  <ShipmentForm onResult={handleShipmentResult} apiStatus={apiStatus} elapsed={elapsed} />
                </motion.div>
              )}
              {step === 2 && shipmentResult && (
                <motion.div key="step2" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                  <AnalysisResult
                    shipmentResult={shipmentResult}
                    onWarehouseResult={handleWarehouseResult}
                    portName={portName}
                    setPortName={setPortName}
                  />
                </motion.div>
              )}
              {step === 3 && warehouseResult && (
                <motion.div key="step3" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                  <WarehouseResult warehouseData={warehouseResult} shipmentResult={shipmentResult} />
                </motion.div>
              )}
            </AnimatePresence>

            {step > 1 && (
              <button onClick={reset} className="mt-4 text-slate-500 text-xs hover:text-slate-300 transition-colors">
                ← 처음부터 다시
              </button>
            )}
          </div>

          {/* 오른쪽: 정보 패널 */}
          <div className="space-y-4">
            {step < 3 && (
              <>
                {/* API 상태 카드 */}
                <div className="card-glass rounded-2xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-white font-medium text-sm">백엔드 API 상태</h4>
                    <StatusBadge status={apiStatus} elapsed={elapsed} />
                  </div>
                  <div className="space-y-2 text-xs text-slate-500">
                    {[
                      { path: '/api/health', desc: '서버 상태' },
                      { path: '/api/mri', desc: '실시간 MRI' },
                      { path: '/api/shipment/register', desc: '화물 등록' },
                      { path: '/api/warehouse/recommend', desc: '창고 추천' },
                      { path: '/api/routy/generate', desc: 'Routy JSON' },
                    ].map(e => (
                      <div key={e.path} className="flex justify-between py-1.5 border-b border-white/5">
                        <code className="text-blue-400">{e.path}</code>
                        <span>{e.desc}</span>
                      </div>
                    ))}
                  </div>
                  {(apiStatus === 'waking' || apiStatus === 'offline') && (
                    <div className="mt-3 p-3 bg-orange-500/10 border border-orange-500/20 rounded-lg text-xs text-orange-300 space-y-1">
                      <div className="font-medium">
                        {apiStatus === 'waking' ? `⏳ 서버 기동 중… (${elapsed}s / 최대 60s)` : '🔄 연결 재시도 중…'}
                      </div>
                      <div className="text-orange-400/70">
                        Render 무료 서버는 15분 비활성 후 슬립됩니다.<br/>
                        첫 요청 시 최대 1분 소요될 수 있습니다.
                      </div>
                      {apiStatus === 'waking' && (
                        <div className="mt-2 h-1 bg-orange-500/20 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-orange-400 rounded-full transition-all duration-1000"
                            style={{ width: `${Math.min((elapsed / 60) * 100, 98)}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 플랫폼 안내 */}
                <div className="card-glass rounded-2xl p-5">
                  <h4 className="text-white font-medium text-sm mb-3">📋 이 플랫폼이 하는 일</h4>
                  <ol className="space-y-2 text-sm text-slate-400">
                    {[
                      '화주 정보를 입력하면 현재 MRI 지수와 리스크 등급을 분석합니다',
                      'MRI ≥ 0.5이면 창고·ODCY 추천이 활성화됩니다',
                      '카카오맵으로 창고 위치를 시각화합니다',
                      'A/B/C/D 4가지 비용 옵션을 비교할 수 있습니다',
                      '최종 선택 시 Routy JSON을 자동 생성합니다',
                    ].map((t, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-blue-400 font-bold flex-shrink-0">{i+1}.</span>
                        {t}
                      </li>
                    ))}
                  </ol>
                </div>
              </>
            )}

            {step === 3 && warehouseResult && (
              <RoutyPanel
                shipmentResult={shipmentResult}
                warehouseResult={warehouseResult}
                formData={formData}
                portName={portName}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
