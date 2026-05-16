import { useRef } from 'react'
import { motion, useInView, useScroll, useTransform } from 'framer-motion'

const steps = [
  {
    step: '01',
    title: '화주 정보 입력',
    desc: '화물 종류, CBM, 출발지·목적지, 납기일, 긴급 여부를 입력합니다. 복잡한 서류 없이 몇 가지 항목만으로 분석을 시작합니다.',
    color: '#2563EB',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    ),
    detail: ['화물 종류 (냉장/일반/위험물)', 'CBM & 납기일 입력', '긴급 화물 플래그 설정'],
  },
  {
    step: '02',
    title: 'MRI 리스크 산출',
    desc: 'AI가 실시간 뉴스, 운임 데이터, 기상 정보를 종합 분석해 현재 해운 리스크 지수를 5개 지표로 산출합니다.',
    color: '#06B6D4',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    detail: ['실시간 RSS 뉴스 NLP 분석', '하이브리드 엔트로피 5차원 가중 산출', 'LSTM 물동량 3개월 예측'],
  },
  {
    step: '03',
    title: '리스크 등급 & 옵션 추천',
    desc: 'MRI 등급(정상/주의/경계/위험)에 따라 과거 유사사례와 현재 이슈를 분석하고, A/B/C 3가지 보관 시나리오 비용과 창고·ODCY 추천을 제공합니다.',
    color: '#8B5CF6',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    detail: ['MRI 4단계 등급 자동 판정', 'A/B/C 3가지 보관 시나리오 비용 비교', '최적 창고·ODCY 자동 추천'],
  },
  {
    step: '04',
    title: 'Routy JSON 자동 생성',
    desc: '출발지→보세창고 운송 지시 JSON을 자동 생성합니다. 선적 재개 시점은 화주가 직접 결정하며, 이후 운송 지시는 별도로 진행됩니다.',
    color: '#10B981',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    detail: ['루티 JSON 생성 (출발지→보세창고)', '루티 배차 API 즉시 연동', '공동물류 그룹 자동 편성'],
  },
]

function Step({ step, index }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, x: index % 2 === 0 ? -50 : 50 }}
      animate={inView ? { opacity: 1, x: 0 } : {}}
      transition={{ duration: 0.6, delay: 0.1 }}
      className={`flex flex-col md:flex-row items-start gap-8 ${index % 2 !== 0 ? 'md:flex-row-reverse' : ''}`}
    >
      {/* Icon + number */}
      <div className="flex-shrink-0">
        <div
          className="w-20 h-20 rounded-2xl flex items-center justify-center relative"
          style={{
            background: `linear-gradient(135deg, ${step.color}30, ${step.color}10)`,
            border: `1px solid ${step.color}40`,
            color: step.color,
            boxShadow: `0 0 30px ${step.color}20`,
          }}
        >
          {step.icon}
          <span
            className="absolute -top-2 -right-2 text-xs font-bold px-1.5 py-0.5 rounded-md"
            style={{ background: step.color, color: 'white' }}
          >
            {step.step}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className={`flex-1 ${index % 2 !== 0 ? 'md:text-right' : ''}`}>
        <h3 className="text-white font-bold text-2xl mb-3">{step.title}</h3>
        <p className="text-slate-400 text-base leading-relaxed mb-5 max-w-lg">{step.desc}</p>
        <ul className={`space-y-2 ${index % 2 !== 0 ? 'md:items-end' : ''} flex flex-col`}>
          {step.detail.map((d) => (
            <li key={d} className="flex items-center gap-2 text-sm text-slate-400">
              {index % 2 !== 0 && <span className="hidden md:block" />}
              <span
                className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{ background: step.color }}
              />
              {d}
            </li>
          ))}
        </ul>
      </div>
    </motion.div>
  )
}

export default function HowItWorks() {
  const containerRef = useRef(null)
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ['start end', 'end start'] })
  const lineHeight = useTransform(scrollYProgress, [0.1, 0.9], ['0%', '100%'])

  return (
    <section id="howitworks" className="py-24 bg-[#0A0F1E] relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 50% 50% at 20% 60%, rgba(37,99,235,0.06) 0%, transparent 70%)' }} />

      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <span className="text-blue-400 text-sm font-medium tracking-widest uppercase">How It Works</span>
          <h2 className="text-4xl md:text-5xl font-bold text-white mt-3 mb-4">
            4단계 스마트 물류 프로세스
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            화물 등록부터 배차 실행까지, AI가 모든 과정을 자동으로 최적화합니다.
          </p>
        </motion.div>

        {/* Timeline */}
        <div ref={containerRef} className="relative">
          {/* Vertical progress line */}
          <div className="absolute left-9 md:left-1/2 top-0 bottom-0 w-px bg-white/5 -translate-x-1/2 hidden md:block" />
          <motion.div
            className="absolute left-9 md:left-1/2 top-0 w-px bg-gradient-to-b from-blue-600 to-cyan-400 -translate-x-1/2 hidden md:block"
            style={{ height: lineHeight }}
          />

          <div className="space-y-20">
            {steps.map((step, i) => (
              <Step key={step.step} step={step} index={i} />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
