import { CLOUDOPS360_REPO, CLOUDRESCUE_REPO, CLOUDRESCUE_URL, NAV_LINKS } from '../config/site.js'
import ExternalLink from './ExternalLink.jsx'
import { Github, Logo } from './Icons.jsx'

const year = new Date().getFullYear()

export default function Footer() {

  return (
    <footer id="github" className="footer">
      <div className="container footer__grid">
        <div className="footer__brand">
          <a className="brand" href="#top" aria-label="Back to top">
            <Logo />
            <span>
              CloudOps<span className="brand__accent">360</span>
            </span>
          </a>
          <p>Infrastructure observability and incident response, built as two connected projects.</p>
        </div>

        <nav aria-label="Footer navigation">
          <h2 className="footer__title">Navigate</h2>
          <ul>
            {NAV_LINKS.filter((link) => link.href !== '#github').map((link) => (
              <li key={link.href}>
                <a href={link.href}>{link.label}</a>
              </li>
            ))}
          </ul>
        </nav>

        <div>
          <h2 className="footer__title">Repositories</h2>
          <ul>
            <li>
              <ExternalLink href={CLOUDOPS360_REPO}>
                <Github width={16} height={16} /> CloudOps360
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={CLOUDRESCUE_REPO}>
                <Github width={16} height={16} /> CloudRescue
              </ExternalLink>
            </li>
            <li>
              <ExternalLink href={CLOUDRESCUE_URL}>CloudRescue live site</ExternalLink>
            </li>
          </ul>
        </div>
      </div>

      <div className="container footer__legal">
        <p>© {year} CloudOps360. Portfolio project — built with React and Vite.</p>
      </div>
    </footer>
  )
}
