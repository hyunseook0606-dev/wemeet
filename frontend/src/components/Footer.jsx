import { motion } from 'framer-motion'

export default function Footer() {
  return (
    <>
      {/* CTA Banner */}
      <section className="py-24 bg-[#0A0F1E] relative overflow-hidden">
        <div className="absolute inset-0"
          style={{ background: 'radial-gradient(ellipse 60% 80% at 50% 50%, rgba(37,99,235,0.15) 0%, transparent 70%)' }} />
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/30 to-transparent" />

        <div className="max-w-4xl mx-auto px-6 text-center relative">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <span className="text-blue-400 text-sm font-medium tracking-widest uppercase">Get Started</span>
            <h2 className="text-4xl md:text-5xl font-bold text-white mt-4 mb-6">
              지금 바로 스마트 물류를<br />
              <span className="text-gradient">경험해 보세요</span>
            </h2>
            <p className="text-slate-400 text-lg mb-10 max-w-2xl mx-auto leading-relaxed">
              바우처 사업을 통해 최대 2억원 지원을 받고
              위밋모빌리티 AI 물류 플랫폼을 도입할 수 있습니다.
            </p>

            <div className="flex flex-wrap gap-4 justify-center">
              <a
                href="mailto:sales@wemeetmobility.com"
                className="px-8 py-4 rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold text-base hover:opacity-90 transition-opacity glow-blue flex items-center gap-2"
              >
                🚀 무료 도입 상담
              </a>
              <a
                href="tel:15330441"
                className="px-8 py-4 rounded-full border border-slate-600 text-slate-300 font-medium text-base hover:border-blue-500 hover:text-blue-300 transition-all"
              >
                1533-0441 전화 문의
              </a>
            </div>

            <p className="text-slate-600 text-sm mt-6">
              평일 10:00 ~ 17:00 · sales@wemeetmobility.com
            </p>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#0A0F1E] border-t border-white/5 py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-8 mb-10">
            {/* Brand */}
            <div className="md:col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <img
                  src="/logo.png"
                  alt="Wemeet Mobility"
                  className="h-8 w-auto"
                  style={{ filter: 'invert(1) hue-rotate(180deg)' }}
                />
              </div>
              <p className="text-slate-500 text-sm leading-relaxed max-w-xs">
                고객의 물류 흐름을 데이터로 진단하고,
                AI 기반 전략으로 최적화하는 공동물류 플랫폼
              </p>
              <div className="flex gap-3 mt-5">
                {['YouTube', 'Blog', 'LinkedIn'].map((s) => (
                  <span
                    key={s}
                    className="px-3 py-1 rounded-md border border-white/10 text-slate-500 text-xs hover:text-white hover:border-white/20 transition-colors cursor-pointer"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {/* Links */}
            <div>
              <h4 className="text-white font-semibold text-sm mb-4">서비스</h4>
              <ul className="space-y-2">
                {['사업 소개', 'LIO 플랫폼', '바우처 사업', '루티(ROOUTY)'].map((l) => (
                  <li key={l}>
                    <a href="#" className="text-slate-500 text-sm hover:text-slate-300 transition-colors">{l}</a>
                  </li>
                ))}
              </ul>
            </div>

            {/* Contact */}
            <div>
              <h4 className="text-white font-semibold text-sm mb-4">연락처</h4>
              <ul className="space-y-2 text-slate-500 text-sm">
                <li>사업제휴: sales@wemeetmobility.com</li>
                <li>채용: recruit@wemeetmobility.com</li>
                <li>대표전화: 1533-0441</li>
                <li className="pt-1 text-slate-600 text-xs">서울 관악구 조원로 5-14, 4-6층</li>
              </ul>
            </div>
          </div>

          <div className="border-t border-white/5 pt-6 flex flex-col md:flex-row items-center justify-between gap-3">
            <p className="text-slate-600 text-xs">
              © 2026 주식회사 위밋모빌리티 · 사업자등록번호 806-87-00694 · CEO 강귀선
            </p>
            <div className="flex gap-4 text-slate-600 text-xs">
              <a href="#" className="hover:text-slate-400 transition-colors">개인정보처리방침</a>
              <a href="#" className="hover:text-slate-400 transition-colors">이용약관</a>
            </div>
          </div>
        </div>
      </footer>
    </>
  )
}
