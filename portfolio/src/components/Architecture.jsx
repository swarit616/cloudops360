import { ARCHITECTURE_LANES } from '../data/content.js'
import Reveal from './Reveal.jsx'
import SectionHeading from './SectionHeading.jsx'

function Lane({ lane }) {
  return (
    <div className="lane">
      <h3 className="lane__label">{lane.label}</h3>
      <ol className="flow">
        {lane.nodes.map((node, index) => (
          <li key={`${lane.id}-${node.title}`} className="flow__item">
            <div className={`node glass ${node.accent ? 'node--accent' : ''}`}>
              <span className="node__title">{node.title}</span>
              <span className="node__detail">{node.detail}</span>
            </div>
            {index < lane.nodes.length - 1 ? (
              <span className="flow__arrow" aria-hidden="true" />
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function Architecture() {
  return (
    <section id="architecture" className="section" aria-labelledby="architecture-title">
      <div className="container">
        <SectionHeading
          id="architecture-title"
          eyebrow="Architecture"
          title="From metric to incident record"
        >
          Metrics flow into Prometheus and Grafana. Alerts take a second path through Alertmanager
          to CloudRescue over an authenticated webhook.
        </SectionHeading>

        <Reveal className="diagram glass" role="group" aria-label="Architecture diagram">
          {ARCHITECTURE_LANES.map((lane) => (
            <Lane key={lane.id} lane={lane} />
          ))}
        </Reveal>

        <div className="notes">
          <Reveal as="p" className="note">
            <strong>Tested end to end.</strong> The CloudRescue integration has been exercised
            through the full alert path, and resolved alerts update the matching incident’s status.
          </Reveal>
          <Reveal as="p" className="note" delay={100}>
            <strong>Scope.</strong> CloudRescue tracks incidents. It does not autonomously repair
            real production infrastructure.
          </Reveal>
        </div>
      </div>
    </section>
  )
}
