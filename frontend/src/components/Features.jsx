import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'

const features = [
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    title: 'MRI 실시간 분석',
    desc: 'IQR 로버스트 엔트로피 기반 5개 차원(G·D·F·V·P)으로 해운 리스크를 실시간 수치화합니다. 2015년 이후 GDELT 및 뉴스 데이터 기반 입니다.',
    color: 'from-blue-600/20 to-blue-600/5',
    accent: '#2563EB',
  },
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    title: 'AI 리스크 등급 엔진',
    desc: 'MRI 4단계 등급(정상·주의·경계·위험, 임계값 0.33/0.43/0.55)으로 리스크를 판정합니다. 과거 7개 유사사례 기반 평균 지연·운임 변동을 참고 제시합니다.',
    color: 'from-cyan-600/20 to-cyan-600/5',
    accent: '#06B6D4',
  },
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    title: '공동물류 최적화',
    desc: '동일 지역·화물 유형 화물을 자동 그룹화하여 LCL 통합 배송을 수행합니다. 보세창고 이용 시 A안 대비 약 37% 비용 절감 효과를 제공합니다.',
    color: 'from-emerald-600/20 to-emerald-600/5',
    accent: '#10B981',
  },
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
    title: 'LSTM 수요 예측',
    desc: '부산항 컨테이너 물동량을 LSTM으로 3개월 선행 예측합니다. MRI 상승/유지/하락 확률과 예측값을 함께 제공하여 의사결정을 지원합니다.',
    color: 'from-purple-600/20 to-purple-600/5',
    accent: '#8B5CF6',
  },
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
    title: '창고·ODCY 추천',
    desc: '거리 기준 5곳 추천. 모든 고객이 이용 가능(MRI 무관)합니다. A(ODCY 10K)/B(CY 30K)/C(보세창고 4K) 3가지 시나리오로 비용을 비교할 수 있습니다.',
    color: 'from-orange-600/20 to-orange-600/5',
    accent: '#F97316',
  },
  {
    icon: (
      <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    ),
    title: 'Routy API 연동',
    desc: '출발지→보세창고 운송 지시서(JSON)를 자동 생성하여 루티(ROOUTY) 배차 API에 즉시 연동합니다. 선적 재개 시점은 화주가 직접 결정합니다.',
    color: 'from-pink-600/20 to-pink-600/5',
    accent: '#EC4899',
  },
]

function FeatureCard({ feature, index }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.55, delay: index * 0.08 }}
      className={`card-glass card-glass-hover rounded-2xl p-6 bg-gradient-to-br ${feature.color} relative overflow-hidden`}
    >
      {/* Top accent line */}
      <div
        className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
        style={{ background: `linear-gradient(to right, ${feature.accent}, transparent)` }}
      />

      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
        style={{ background: `${feature.accent}20`, color: feature.accent }}
      >
        {feature.icon}
      </div>

      <h3 className="text-white font-semibold text-lg mb-2">{feature.title}</h3>
      <p className="text-slate-400 text-sm leading-relaxed">{feature.desc}</p>
    </motion.div>
  )
}

export default function Features() {
  return (
    <section id="features" className="py-24 bg-[#0A0F1E] relative">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 60% 40% at 80% 30%, rgba(6,182,212,0.06) 0%, transparent 70%)' }} />

      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="text-cyan-400 text-sm font-medium tracking-widest uppercase">Platform Capabilities</span>
          <h2 className="text-4xl md:text-5xl font-bold text-white mt-3 mb-4">
            하나의 플랫폼,<br />
            <span className="text-gradient">모든 물류 솔루션</span>
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            AI·빅데이터·딥러닝 기술을 결합한 통합 공동물류 플랫폼으로
            규모에 관계없이 누구나 스마트 물류를 도입할 수 있습니다.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f, i) => (
            <FeatureCard key={f.title} feature={f} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}
