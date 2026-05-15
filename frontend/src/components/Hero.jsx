import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { gsap } from 'gsap'

// Canvas particle / route network animation
function ParticleCanvas() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let animId

    const resize = () => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    // Nodes representing port cities
    const nodes = [
      { x: 0.15, y: 0.4, label: '부산' },
      { x: 0.32, y: 0.25, label: '상하이' },
      { x: 0.48, y: 0.55, label: '싱가포르' },
      { x: 0.62, y: 0.2, label: '로테르담' },
      { x: 0.75, y: 0.6, label: 'LA' },
      { x: 0.88, y: 0.35, label: '두바이' },
      { x: 0.25, y: 0.7, label: '도쿄' },
      { x: 0.55, y: 0.38, label: '홍콩' },
    ]

    const edges = [
      [0, 1], [0, 6], [1, 7], [1, 2], [2, 4], [2, 3],
      [3, 5], [4, 5], [7, 3], [6, 4], [0, 7],
    ]

    // Moving particles along edges
    const particles = edges.map(([a, b]) => ({
      a, b,
      t: Math.random(),
      speed: 0.0008 + Math.random() * 0.001,
    }))

    // Background stars
    const stars = Array.from({ length: 80 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: Math.random() * 1.2,
      alpha: 0.1 + Math.random() * 0.4,
    }))

    const draw = () => {
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      // Stars
      stars.forEach(s => {
        ctx.beginPath()
        ctx.arc(s.x * W, s.y * H, s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(148,163,184,${s.alpha})`
        ctx.fill()
      })

      // Edges
      edges.forEach(([a, b]) => {
        const na = nodes[a], nb = nodes[b]
        const grad = ctx.createLinearGradient(na.x * W, na.y * H, nb.x * W, nb.y * H)
        grad.addColorStop(0, 'rgba(37,99,235,0.25)')
        grad.addColorStop(1, 'rgba(6,182,212,0.15)')
        ctx.beginPath()
        ctx.moveTo(na.x * W, na.y * H)
        ctx.lineTo(nb.x * W, nb.y * H)
        ctx.strokeStyle = grad
        ctx.lineWidth = 1
        ctx.stroke()
      })

      // Nodes
      nodes.forEach(n => {
        // Outer glow ring
        const grd = ctx.createRadialGradient(n.x * W, n.y * H, 2, n.x * W, n.y * H, 14)
        grd.addColorStop(0, 'rgba(37,99,235,0.5)')
        grd.addColorStop(1, 'rgba(37,99,235,0)')
        ctx.beginPath()
        ctx.arc(n.x * W, n.y * H, 14, 0, Math.PI * 2)
        ctx.fillStyle = grd
        ctx.fill()
        // Core dot
        ctx.beginPath()
        ctx.arc(n.x * W, n.y * H, 3.5, 0, Math.PI * 2)
        ctx.fillStyle = '#60A5FA'
        ctx.fill()
        // Label
        ctx.fillStyle = 'rgba(148,163,184,0.7)'
        ctx.font = '11px sans-serif'
        ctx.fillText(n.label, n.x * W + 7, n.y * H - 5)
      })

      // Moving particles
      particles.forEach(p => {
        p.t += p.speed
        if (p.t > 1) p.t = 0
        const na = nodes[p.a], nb = nodes[p.b]
        const px = (na.x + (nb.x - na.x) * p.t) * W
        const py = (na.y + (nb.y - na.y) * p.t) * H
        // Trail
        const trail = ctx.createRadialGradient(px, py, 0, px, py, 6)
        trail.addColorStop(0, 'rgba(6,182,212,0.9)')
        trail.addColorStop(1, 'rgba(6,182,212,0)')
        ctx.beginPath()
        ctx.arc(px, py, 6, 0, Math.PI * 2)
        ctx.fillStyle = trail
        ctx.fill()
        ctx.beginPath()
        ctx.arc(px, py, 2.5, 0, Math.PI * 2)
        ctx.fillStyle = '#ffffff'
        ctx.fill()
      })

      animId = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full opacity-60"
      style={{ zIndex: 0 }}
    />
  )
}

const heroWords = ['스마트', 'AI 기반', '데이터 중심']

export default function Hero() {
  const wordRef = useRef(null)
  const wordIdx = useRef(0)

  useEffect(() => {
    const words = heroWords
    const el = wordRef.current
    if (!el) return

    const cycle = () => {
      gsap.to(el, {
        opacity: 0, y: -20, duration: 0.4,
        onComplete: () => {
          wordIdx.current = (wordIdx.current + 1) % words.length
          el.textContent = words[wordIdx.current]
          gsap.fromTo(el, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.5 })
        }
      })
    }
    const id = setInterval(cycle, 2400)
    return () => clearInterval(id)
  }, [])

  return (
    <section className="relative min-h-screen flex items-center overflow-hidden bg-[#0A0F1E]">

      {/* ── Right-side video panel (50% width → less stretch → better quality) ── */}
      <div
        className="absolute top-0 right-0 h-full w-1/2"
        style={{ zIndex: 0 }}
      >
        <video
          src="/truck.mp4"
          autoPlay
          loop
          muted
          playsInline
          className="w-full h-full object-cover"
        />
        {/* Left fade: video blends into dark background */}
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(to right, #0A0F1E 0%, rgba(10,15,30,0.3) 40%, transparent 100%)',
          }}
        />
        {/* Bottom fade */}
        <div
          className="absolute bottom-0 left-0 right-0 h-48"
          style={{ background: 'linear-gradient(to bottom, transparent, #0A0F1E)' }}
        />
      </div>

      {/* Left dark base */}
      <div
        className="absolute top-0 left-0 h-full w-1/2"
        style={{ background: '#0A0F1E', zIndex: 0 }}
      />

      {/* Subtle particle network */}
      <div className="absolute inset-0 opacity-20" style={{ zIndex: 1 }}>
        <ParticleCanvas />
      </div>

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 h-40"
        style={{ background: 'linear-gradient(to bottom, transparent, #0A0F1E)', zIndex: 2 }}
      />

      {/* Content */}
      <div className="relative max-w-7xl mx-auto px-6 pt-28 pb-20 w-full" style={{ zIndex: 4 }}>
        <div className="max-w-3xl">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 mb-6"
          >
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-cyan-300 text-sm font-medium">
              공동물류 AI 플랫폼 · 위밋모빌리티
            </span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="text-5xl md:text-6xl lg:text-7xl font-bold leading-tight text-white mb-6"
          >
            <span ref={wordRef} className="text-gradient inline-block">
              스마트
            </span>{' '}
            물류의{' '}
            <br className="hidden md:block" />
            새로운 기준
          </motion.h1>

          {/* Sub */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="text-slate-300 text-lg md:text-xl leading-relaxed mb-10 max-w-2xl"
          >
            고객의 물류 흐름을 실시간 데이터로 진단하고,{' '}
            <br className="hidden sm:block" />
            AI 기반 시나리오 엔진으로 최적화하는 공동물류 플랫폼
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.45 }}
            className="flex flex-wrap gap-4"
          >
            <a
              href="#live"
              className="group px-7 py-3.5 rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-semibold text-base hover:opacity-90 transition-all duration-200 glow-blue flex items-center gap-2"
            >
              실시간 MRI 확인
              <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </a>
            <a
              href="mailto:sales@wemeetmobility.com"
              className="px-7 py-3.5 rounded-full border border-white/20 text-slate-300 font-medium text-base hover:border-blue-500 hover:text-blue-300 transition-all duration-200"
            >
              도입 문의
            </a>
          </motion.div>

          {/* Quick stats row */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.6 }}
            className="mt-14 flex flex-wrap gap-8"
          >
            {[
              { value: '28%', label: '물류비 절감' },
              { value: '99.5%', label: '배송 정확도' },
              { value: '3,000+', label: '가입 기업' },
            ].map((s) => (
              <div key={s.label}>
                <div className="text-2xl font-bold text-gradient">{s.value}</div>
                <div className="text-slate-400 text-sm mt-0.5">{s.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
        style={{ zIndex: 4 }}
      >
        <span className="text-slate-500 text-xs tracking-widest uppercase">Scroll</span>
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
          className="w-0.5 h-8 bg-gradient-to-b from-blue-500 to-transparent"
        />
      </motion.div>
    </section>
  )
}
