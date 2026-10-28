import { TECH_GROUPS } from '../data/content.js'
import Reveal from './Reveal.jsx'
import SectionHeading from './SectionHeading.jsx'

function monogram(name) {
  const words = name.split(' ')
  return words.length > 1 ? words.map((w) => w[0]).join('').slice(0, 2) : name.slice(0, 2)
}

export default function TechStack() {
  return (
    <section id="technology" className="section" aria-labelledby="technology-title">
      <div className="container">
        <SectionHeading id="technology-title" eyebrow="Technology" title="The stack behind it">
          Open tooling for observability, a small API service, and optional cloud SDKs.
        </SectionHeading>

        <div className="tech">
          {TECH_GROUPS.map((group, index) => (
            <Reveal key={group.title} delay={index * 90} className="tech__group">
              <h3>{group.title}</h3>
              <ul className="tech__list">
                {group.items.map((item) => (
                  <li key={item.name} className="chip glass">
                    <span className="chip__mark" aria-hidden="true">
                      {monogram(item.name)}
                    </span>
                    <span className="chip__text">
                      <span className="chip__name">{item.name}</span>
                      <span className="chip__note">{item.note}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </Reveal>
          ))}
        </div>

        <Reveal as="p" className="note note--muted">
          Built with optional AWS and Azure SDK integrations, designed to be enabled and extended
          as deployment requirements evolve.
        </Reveal>
      </div>
    </section>
  )
}
