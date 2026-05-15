import { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { api } from '../hooks/useApi'

const MRI_GRADES = [
  { grade: '위험', range: '0.55 이상', color: '#EF4444', min: 0.55, max: 1.01, icon: '🔴' },
  { grade: '경계', range: '0.43 ~ 0.55', color: '#F97316', min: 0.43, max: 0.55, icon: '🟠' },
  { grade: '주의', range: '0.33 ~ 0.43', color: '#EAB308', min: 0.33, max: 0.43, icon: '🟡' },
  { grade: '정상', range: '0.33 미만', color: '#22C55E', min: 0.0, max: 0.33, icon: '🟢' },
]

function getMRIColor(mri) {
  if (mri >= 0.55) return '#EF4444'
  if (mri >= 0.43) return '#F97316'
  if (mri >= 0.33) return '#EAB308'
  return '#22C55E'
}

// Circular gauge
function MRIGauge({ value }) {
  const r = 80
  const stroke = 10
  const normalizedR = r - stroke / 2
  const circumference = 2 * Math.PI * normalizedR
  // 270° arc (from 135° to 405°)
  const arcLen = circumference * 0.75
  const offset = arcLen - (value / 1) * arcLen

  const color = value >= 0.55 ? '#EF4444' : value >= 0.43 ? '#F97316' : value >= 0.33 ? '#EAB308' : '#22C55E'

  return (
    <svg width={r * 2} height={r * 2} className="overflow-visible">
      {/* Background track */}
      <circle
        cx={r} cy={r} r={normalizedR}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth={stroke}
        strokeDasharray={`${arcLen} ${circumference}`}
        strokeDashoffset={0}
        strokeLinecap="round"
        transform={`rotate(135 ${r} ${r})`}
      />
      {/* Value arc */}
      <circle
        cx={r} cy={r} r={normalizedR}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeDasharray={`${arcLen} ${circumference}`}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(135 ${r} ${r})`}
        style={{
          filter: `drop-shadow(0 0 8px ${color})`,
          transition: 'stroke-dashoffset 1s ease, stroke 0.5s ease',
        }}
      />
      {/* Center text */}
      <text x={r} y={r - 6} textAnchor="middle" fill="white" fontSize="26" fontWeight="700">
        {(value * 100).toFixed(0)}
      </text>
      <text x={r} y={r + 14} textAnchor="middle" fill="rgba(148,163,184,0.8)" fontSize="11">
        MRI
      </text>
    </svg>
  )
}

// Fallback mock data when API is unavailable
const MOCK_DATA = {
  mri: 0.38,
  grade: '🟡 주의',
  top_category: '운임급등',
  current_issue: '글로벌 운임 상승세 지속 중',
  top_keywords: ['운임', '급등', 'SCFI', '선복', '부족'],
  data_source: 'mock',
}

export default function LiveMRI() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const sectionRef = useRef(null)

  const fetchMRI = async (force = false) => {
    setLoading(true)
    try {
      const res = await api.get(`/mri${force ? '?refresh=true' : ''}`, { timeout: 90000 })
      setData(res.data)
      setError(false)
    } catch {
      setData(MOCK_DATA)
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMRI()
    const id = setInterval(() => fetchMRI(), 3600000) // 1시간마다 자동 갱신
    return () => clearInterval(id)
  }, [])

  const mriColor = getMRIColor(data?.mri ?? 0)

  return (
    <section id="live" ref={sectionRef} className="py-24 bg-[#0D1627] relative overflow-hidden">
      {/* Decorative glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-1 bg-gradient-to-r from-transparent via-blue-500 to-transparent" />

      <div className="max-w-7xl mx-auto px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-14"
        >
          <span className="text-blue-400 text-sm font-medium tracking-widest uppercase">Real-time Dashboard</span>
          <h2 className="text-4xl md:text-5xl font-bold text-white mt-3 mb-4">
            실시간 해운 리스크 현황
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            AI가 실시간으로 분석하는 해운 리스크 지수(MRI)와 최적 대응 시나리오
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-8 items-start">
          {/* MRI Gauge Card */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="card-glass rounded-2xl p-8"
          >
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-white font-semibold text-lg">Maritime Risk Index</h3>
                <p className="text-slate-500 text-sm mt-0.5">해운 리스크 지수</p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${loading ? 'bg-yellow-400' : error ? 'bg-red-400' : 'bg-green-400 animate-pulse'}`} />
                <span className="text-slate-500 text-xs">
                  {loading ? '로딩 중' : error ? '데모 모드' : data?.data_source === 'realtime' ? `실시간 (뉴스 ${data.news_count}건)` : '시뮬레이션'}
                </span>
              </div>
            </div>

            {loading ? (
              <div className="flex justify-center py-12">
                <div className="w-16 h-16 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
              </div>
            ) : (
              <div className="flex flex-col items-center gap-6">
                <MRIGauge value={data?.mri ?? 0} />

                {/* Grade badge */}
                <div
                  className="px-4 py-2 rounded-full text-sm font-semibold"
                  style={{
                    background: `${mriColor}20`,
                    border: `1px solid ${mriColor}50`,
                    color: mriColor,
                  }}
                >
                  {data?.grade ?? '—'}
                </div>

                {/* MRI breakdown bars */}
                <div className="w-full space-y-3">
                  {[
                    { label: '지정학 리스크 (G)', pct: Math.min((data?.mri ?? 0) * 120, 100) },
                    { label: '지연 지수 (D)', pct: Math.min((data?.mri ?? 0) * 90, 100) },
                    { label: '운임 변동 (F)', pct: Math.min((data?.mri ?? 0) * 100, 100) },
                  ].map((item) => (
                    <div key={item.label}>
                      <div className="flex justify-between text-xs text-slate-500 mb-1">
                        <span>{item.label}</span>
                        <span>{item.pct.toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          whileInView={{ width: `${item.pct}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 1, delay: 0.3 }}
                          className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-400"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>

          {/* Right side: 현재 이슈 + 등급 기준 */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="space-y-4"
          >
            {/* 현재 이슈 카드 */}
            <div className="card-glass rounded-2xl p-6">
              <h3 className="text-white font-semibold mb-4">현재 이슈 요약</h3>
              {loading ? (
                <div className="h-20 bg-white/5 rounded-xl animate-pulse" />
              ) : (
                <div className="space-y-4">
                  <div
                    className="rounded-xl p-4"
                    style={{
                      background: `${mriColor}15`,
                      border: `1px solid ${mriColor}40`,
                    }}
                  >
                    <div className="text-white font-medium text-sm mb-1">
                      {data?.current_issue ?? '이슈 정보 없음'}
                    </div>
                    <div className="text-slate-400 text-xs">
                      주요 카테고리: <span className="text-slate-300">{data?.top_category ?? data?.category ?? '—'}</span>
                    </div>
                    {error && (
                      <div className="text-slate-500 text-xs mt-2">* 백엔드 미연결 — 데모 데이터 표시 중</div>
                    )}
                  </div>
                  {(data?.top_keywords?.length ?? 0) > 0 && (
                    <div>
                      <div className="text-slate-500 text-xs mb-2">주요 뉴스 키워드</div>
                      <div className="flex flex-wrap gap-1.5">
                        {data.top_keywords.slice(0, 6).map((kw, i) => (
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
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* MRI 등급 기준 카드 */}
            <div className="card-glass rounded-2xl p-6">
              <h3 className="text-white font-semibold mb-4">MRI 등급 기준</h3>
              <div className="space-y-2">
                {MRI_GRADES.map(({ grade, range, color, min, max, icon }) => {
                  const mriVal = data?.mri ?? 0
                  const isActive = mriVal >= min && mriVal < max
                  return (
                    <div
                      key={grade}
                      className="flex items-center justify-between py-2.5 px-3 rounded-lg transition-all"
                      style={{
                        background: isActive ? `${color}15` : 'transparent',
                        border: `1px solid ${isActive ? color + '40' : 'transparent'}`,
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg">{icon}</span>
                        <div>
                          <div className="text-white text-sm font-medium">{grade}</div>
                          <div className="text-slate-500 text-xs">{range}</div>
                        </div>
                      </div>
                      {isActive && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-medium"
                          style={{ background: `${color}20`, color }}
                        >
                          현재
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Refresh buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => fetchMRI(false)}
                className="flex-1 py-3 rounded-xl border border-blue-500/30 text-blue-400 text-sm hover:bg-blue-500/10 transition-all flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                캐시 조회
              </button>
              <button
                onClick={() => fetchMRI(true)}
                className="flex-1 py-3 rounded-xl border border-green-500/30 text-green-400 text-sm hover:bg-green-500/10 transition-all flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                실시간 수집
              </button>
            </div>
            {data?.cached_at && (
              <p className="text-center text-slate-600 text-xs mt-1">마지막 수집: {data.cached_at}</p>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
