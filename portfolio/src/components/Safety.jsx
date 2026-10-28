import { SAFETY_ITEMS } from '../data/content.js'
import Reveal from './Reveal.jsx'
import SectionHeading from './SectionHeading.jsx'
import { Shield } from './Icons.jsx'

export default function Safety() {
  return (
    <section id="safety" className="section" aria-labelledby="safety-title">
      <div className="container">
        <SectionHeading
          id="safety-title"
          eyebrow="Engineering & safety"
          title="Cautious by design"
        >
          Operational tooling can do damage. CloudOps360 is built so that doing nothing is the
          default.
        </SectionHeading>

        <ul className="safety">
          {SAFETY_ITEMS.map((item, index) => (
            <Reveal as="li" key={item.title} delay={(index % 3) * 90} className="safety__item glass">
              <Shield className="safety__icon" />
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  )
}
