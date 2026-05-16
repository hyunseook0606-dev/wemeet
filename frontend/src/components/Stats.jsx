import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'

const partners = [
  'CJ대한통운', 'LX판토스', '한국해양수산개발원', '부산항만공사',
  '루티(ROOUTY)', '카카오모빌리티', 'ShipGo', 'LinGo',
]

const timeline = [
  { year: '2018', event: '위밋모빌리티 창립' },
  { year: '2021', event: '루티(ROOUTY) 서비스 출시' },
  { year: '2024', event: '물류 AI 플랫폼 고도화' },
  { year: '2025', event: '소화물통합물류협동조합 등록' },
  { year: '2026', event: '공동물류 플랫폼 런칭' },
]

export default function Stats() {
  return (
    <>
      {/* Timeline */}
      <section className="py-20 bg-[#0A0F1E]">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <span className="text-cyan-400 text-sm font-medium tracking-widest uppercase">Timeline</span>
            <h2 className="text-3xl font-bold text-white mt-3">성장의 발자취</h2>
          </motion.div>

          <div className="flex flex-col md:flex-row items-start md:items-center gap-0 relative">
            <div className="hidden md:block absolute top-5 left-0 right-0 h-px bg-gradient-to-r from-blue-600/30 via-cyan-500/30 to-blue-600/30" />
            {timeline.map((t, i) => (
              <motion.div
                key={t.year}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex-1 flex flex-col items-center text-center px-4 mb-8 md:mb-0"
              >
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-600 to-cyan-500 flex items-center justify-center text-white text-xs font-bold mb-3 relative z-10 glow-blue">
                  {i + 1}
                </div>
                <div className="text-blue-400 font-bold text-lg">{t.year}</div>
                <div className="text-slate-400 text-sm mt-1 leading-snug">{t.event}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Partners */}
      <section id="news" className="py-20 bg-[#0D1627]">
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent" />
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-10"
          >
            <span className="text-slate-500 text-sm font-medium tracking-widest uppercase">Partners & Clients</span>
            <h2 className="text-3xl font-bold text-white mt-3">함께하는 파트너</h2>
          </motion.div>

          {/* Marquee */}
          <div className="overflow-hidden relative">
            <div className="absolute left-0 top-0 bottom-0 w-20 z-10"
              style={{ background: 'linear-gradient(to right, #0D1627, transparent)' }} />
            <div className="absolute right-0 top-0 bottom-0 w-20 z-10"
              style={{ background: 'linear-gradient(to left, #0D1627, transparent)' }} />
            <motion.div
              animate={{ x: ['0%', '-50%'] }}
              transition={{ duration: 18, repeat: Infinity, ease: 'linear' }}
              className="flex gap-6 whitespace-nowrap"
            >
              {[...partners, ...partners].map((p, i) => (
                <div
                  key={i}
                  className="flex-shrink-0 px-6 py-3 rounded-xl card-glass text-slate-400 text-sm font-medium hover:text-white transition-colors"
                >
                  {p}
                </div>
              ))}
            </motion.div>
          </div>
        </div>
      </section>
    </>
  )
}
