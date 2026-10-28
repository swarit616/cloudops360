import { CLOUDOPS360_REPO, CLOUDRESCUE_REPO, CLOUDRESCUE_URL } from '../config/site.js'
import { PROJECTS } from '../data/content.js'
import ExternalLink from './ExternalLink.jsx'
import Reveal from './Reveal.jsx'
import SectionHeading from './SectionHeading.jsx'
import { ArrowUpRight, Check, Github } from './Icons.jsx'

const LINKS = {
  cloudops360: [{ label: 'GitHub repository', href: CLOUDOPS360_REPO, icon: <Github /> }],
  cloudrescue: [
    { label: 'Live deployment', href: CLOUDRESCUE_URL, icon: <ArrowUpRight />, primary: true },
    { label: 'GitHub repository', href: CLOUDRESCUE_REPO, icon: <Github /> },
  ],
}

export default function Projects() {
  return (
    <section id="overview" className="section" aria-labelledby="overview-title">
      <div className="container">
        <SectionHeading
          id="overview-title"
          eyebrow="Overview"
          title="Two connected projects, one workflow"
        >
          CloudOps360 observes the infrastructure. CloudRescue tracks what goes wrong. Together they
          cover the path from a metric to an incident record.
        </SectionHeading>

        <div className="cards">
          {PROJECTS.map((project, index) => (
            <Reveal
              as="article"
              key={project.id}
              delay={index * 110}
              className={`card card--${project.id}`}
              aria-labelledby={`${project.id}-title`}
            >
              <p className="card__kicker">{project.kicker}</p>
              <h3 id={`${project.id}-title`}>{project.name}</h3>
              <p className="card__summary">{project.summary}</p>
              <ul className="checklist">
                {project.points.map((point) => (
                  <li key={point}>
                    <Check /> <span>{point}</span>
                  </li>
                ))}
              </ul>
              <ul className="tags" aria-label={`${project.name} technologies`}>
                {project.tags.map((tag) => (
                  <li key={tag}>{tag}</li>
                ))}
              </ul>
              <div className="card__actions">
                {LINKS[project.id].map((link) => (
                  <ExternalLink
                    key={link.href}
                    href={link.href}
                    className={`btn ${link.primary ? 'btn--primary' : 'btn--ghost'}`}
                  >
                    {link.icon} {link.label}
                  </ExternalLink>
                ))}
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
