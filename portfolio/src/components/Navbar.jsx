import { useEffect, useState } from 'react'
import { CLOUDRESCUE_URL, NAV_LINKS } from '../config/site.js'
import ExternalLink from './ExternalLink.jsx'
import { ArrowUpRight, Close, Logo, Menu } from './Icons.jsx'

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const onResize = () => {
      if (window.innerWidth >= 960) setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onResize)
    }
  }, [open])

  const close = () => setOpen(false)

  return (
    <header className={`navbar ${scrolled ? 'is-scrolled' : ''} ${open ? 'is-open' : ''}`}>
      <div className="container navbar__inner">
        <a className="brand" href="#top" onClick={close} aria-label="CloudOps360 home">
          <Logo />
          <span>
            CloudOps<span className="brand__accent">360</span>
          </span>
        </a>

        <nav id="primary-nav" className="navbar__links" aria-label="Primary">
          <ul>
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <a href={link.href} onClick={close}>
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
          <ExternalLink
            href={CLOUDRESCUE_URL}
            className="btn btn--primary navbar__cta navbar__cta--mobile"
            onClick={close}
          >
            Live Demo <ArrowUpRight />
          </ExternalLink>
        </nav>

        <ExternalLink href={CLOUDRESCUE_URL} className="btn btn--primary navbar__cta navbar__cta--desktop">
          Live Demo <ArrowUpRight />
        </ExternalLink>

        <button
          type="button"
          className="navbar__toggle"
          aria-expanded={open}
          aria-controls="primary-nav"
          aria-label={open ? 'Close menu' : 'Open menu'}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <Close /> : <Menu />}
        </button>
      </div>
    </header>
  )
}
