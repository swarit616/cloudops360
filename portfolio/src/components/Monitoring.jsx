import { DASHBOARD_SCREENSHOT, GRAFANA_URL } from '../config/site.js'
import { DASHBOARD_PANELS } from '../data/content.js'
import ExternalLink from './ExternalLink.jsx'
import Reveal from './Reveal.jsx'
import SectionHeading from './SectionHeading.jsx'
import { ArrowUpRight } from './Icons.jsx'

function isPublicUrl(value) {
  try {
    const url = new URL(value)
    const host = url.hostname
    const local =
      host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0' || host === '[::1]'
    return url.protocol === 'https:' && !local
  } catch {
    return false
  }
}

export default function Monitoring() {
  const hasGrafana = isPublicUrl(GRAFANA_URL)

  return (
    <section id="monitoring" className="section" aria-labelledby="monitoring-title">
      <div className="container">
        <SectionHeading
          id="monitoring-title"
          eyebrow="Monitoring"
          title="A 34-panel Grafana dashboard"
        >
          The CloudOps360 dashboard brings host, application and integration signals into a single
          view.
        </SectionHeading>

        <div className="monitoring">
          <Reveal className="shot glass">
            {DASHBOARD_SCREENSHOT ? (
              <img
                src={DASHBOARD_SCREENSHOT}
                alt="CloudOps360 Grafana dashboard"
                loading="lazy"
                decoding="async"
              />
            ) : (
              <div className="shot__placeholder" role="img" aria-label="Placeholder for a Grafana dashboard screenshot">
                <div className="shot__bar" aria-hidden="true">
                  <i /> <i /> <i />
                </div>
                <div className="shot__grid" aria-hidden="true">
                  {Array.from({ length: 12 }, (_, i) => (
                    <span key={i} className={i % 5 === 0 ? 'wide' : ''} />
                  ))}
                </div>
                <p className="shot__text">Dashboard screenshot placeholder</p>
              </div>
            )}
          </Reveal>

          <Reveal className="monitoring__side" delay={120}>
            <h3>What the dashboard covers</h3>
            <ul className="panel-list">
              {DASHBOARD_PANELS.map((panel) => (
                <li key={panel}>{panel}</li>
              ))}
            </ul>
            {hasGrafana ? (
              <ExternalLink className="btn btn--primary" href={GRAFANA_URL}>
                Open live dashboard <ArrowUpRight />
              </ExternalLink>
            ) : (
              <p className="coming-soon" role="status">
                Local Deployment · Dashboard Preview Available
              </p>
            )}
          </Reveal>
        </div>
      </div>
    </section>
  )
}
