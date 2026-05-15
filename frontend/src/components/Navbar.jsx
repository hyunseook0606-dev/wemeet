import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const navLinks = [
  { label: '서비스 소개', href: '#features' },
  { label: '플랫폼', href: '#platform' },
  { label: '도입 절차', href: '#howitworks' },
  { label: '실시간 현황', href: '#live' },
  { label: '회사 소식', href: '#news' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 bg-[#0A0F1E] ${
        scrolled ? 'backdrop-blur-md border-b border-white/5' : ''
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <a href="#">
          <img
            src="/logo.png"
            alt="Wemeet Mobility"
            className="h-8 w-auto"
            style={{ filter: 'invert(1) hue-rotate(180deg)' }}
          />
        </a>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-slate-400 hover:text-white text-sm transition-colors duration-200"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">
          <a
            href="mailto:sales@wemeetmobility.com"
            className="px-5 py-2 rounded-full border border-blue-500/50 text-blue-400 text-sm hover:bg-blue-500/10 transition-all duration-200"
          >
            문의하기
          </a>
          <a
            href="#live"
            className="px-5 py-2 rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white text-sm font-medium hover:opacity-90 transition-opacity glow-blue"
          >
            플랫폼 체험
          </a>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-slate-300 p-1"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          <div className="w-6 flex flex-col gap-1.5">
            <span className={`block h-0.5 bg-current transition-all ${menuOpen ? 'rotate-45 translate-y-2' : ''}`} />
            <span className={`block h-0.5 bg-current transition-all ${menuOpen ? 'opacity-0' : ''}`} />
            <span className={`block h-0.5 bg-current transition-all ${menuOpen ? '-rotate-45 -translate-y-2' : ''}`} />
          </div>
        </button>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden bg-[#0D1627] border-t border-white/5 px-6 pb-6"
          >
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="block py-3 text-slate-300 hover:text-white border-b border-white/5 text-sm"
              >
                {link.label}
              </a>
            ))}
            <a
              href="mailto:sales@wemeetmobility.com"
              className="mt-4 block text-center py-2.5 rounded-full border border-blue-500/50 text-blue-400 text-sm"
            >
              문의하기
            </a>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  )
}
