import './App.css'
import Navbar from './components/Navbar.jsx'
import Hero from './components/Hero.jsx'
import Projects from './components/Projects.jsx'
import Architecture from './components/Architecture.jsx'
import Monitoring from './components/Monitoring.jsx'
import IncidentResponse from './components/IncidentResponse.jsx'
import TechStack from './components/TechStack.jsx'
import Safety from './components/Safety.jsx'
import Footer from './components/Footer.jsx'

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Navbar />
      <main id="main">
        <Hero />
        <Projects />
        <Architecture />
        <Monitoring />
        <IncidentResponse />
        <TechStack />
        <Safety />
      </main>
      <Footer />
    </>
  )
}
