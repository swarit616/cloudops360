import { CLOUDRESCUE_URL } from '../config/site.js'
import { INCIDENT_STEPS } from '../data/content.js'
import ExternalLink from './ExternalLink.jsx'
import Reveal from './Reveal.jsx'
import SectionHeading from './SectionHeading.jsx'
import { ArrowUpRight } from './Icons.jsx'

export default function IncidentResponse() {
  return (
    <section id="incident-response" className="section" aria-labelledby="incident-title">
      <div className="container">
        <SectionHeading
          id="incident-title"
          eyebrow="Incident response"
          title="The tested alert-to-incident workflow"
        >
          Five steps connect a firing Prometheus alert to a tracked, resolvable incident in
          CloudRescue.
        </SectionHeading>

        <ol className="steps">
          {INCIDENT_STEPS.map((step, index) => (
            <Reveal as="li" key={step.title} delay={index * 80} className="step glass">
              <span className="step__num" aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </Reveal>
          ))}
        </ol>

        <div className="split">
          <Reveal className="split__item">
            <h3>Live Monitoring</h3>
            <p>
              Incidents created from real Alertmanager webhooks appear in CloudRescue’s Live
              Monitoring view and follow the alert’s firing and resolved states.
            </p>
          </Reveal>
          <Reveal className="split__item" delay={100}>
            <h3>Demo simulation</h3>
            <p>
              CloudRescue also includes a separate demo simulation. It is independent of live
              monitoring and exists so the workflow can be explored without real alerts.
            </p>
          </Reveal>
        </div>

        <Reveal className="center">
          <ExternalLink className="btn btn--primary" href={CLOUDRESCUE_URL}>
            Visit CloudRescue <ArrowUpRight />
          </ExternalLink>
        </Reveal>
      </div>
    </section>
  )
}
