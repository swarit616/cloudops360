import { CLOUDOPS360_REPO, CLOUDRESCUE_URL } from '../config/site.js'
import ExternalLink from './ExternalLink.jsx'
import MonitoringVisual from './MonitoringVisual.jsx'
import { ArrowRight, ArrowUpRight, Github } from './Icons.jsx'

export default function Hero() {
  return (
    <section id="top" className="hero" aria-labelledby="hero-title">
      <div className="hero__glow" aria-hidden="true" />
      <div className="container hero__grid">
        <div className="hero__copy">
          <p className="eyebrow">Cloud &amp; DevOps engineering portfolio</p>
          <h1 id="hero-title">
            Monitor Infrastructure. Detect Issues.{' '}
            <span className="text-gradient">Respond with Confidence.</span>
          </h1>
          <p className="lede">
            CloudOps360 and CloudRescue demonstrate an integrated infrastructure observability and
            incident-response workflow: metrics are collected and visualised, alerts are routed, and
            incidents are tracked from firing to resolved.
          </p>
          <div className="hero__actions">
            <a className="btn btn--primary" href="#overview">
              Explore CloudOps360 <ArrowRight />
            </a>
            <ExternalLink className="btn btn--ghost" href={CLOUDRESCUE_URL}>
              Open CloudRescue <ArrowUpRight />
            </ExternalLink>
          </div>
          <ExternalLink className="text-link" href={CLOUDOPS360_REPO}>
            <Github /> View source on GitHub
          </ExternalLink>
        </div>
        <div className="hero__visual">
          <MonitoringVisual />
        </div>
      </div>
    </section>
  )
}
