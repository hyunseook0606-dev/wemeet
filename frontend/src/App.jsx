import './index.css'
import Navbar from './components/Navbar'
import Hero from './components/Hero'
import Features from './components/Features'
import LiveMRI from './components/LiveMRI'
import HowItWorks from './components/HowItWorks'
import Platform from './components/Platform'
import Stats from './components/Stats'
import Footer from './components/Footer'

export default function App() {
  return (
    <div className="min-h-screen bg-[#0A0F1E]">
      <Navbar />
      <Hero />
      <Features />
      <LiveMRI />
      <HowItWorks />
      <Platform />
      <Stats />
      <Footer />
    </div>
  )
}
