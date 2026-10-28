// Central configuration for links and optional deployment settings.
// Nothing here is secret — this file ships to the browser.

export const CLOUDRESCUE_URL = 'https://cloudrescue.onrender.com/'

export const CLOUDOPS360_REPO = 'https://github.com/swarit616/cloudops360'
export const CLOUDRESCUE_REPO = 'https://github.com/swarit616/cloudrescue'

/**
 * Public Grafana URL (read-only / anonymous viewer recommended).
 *
 * Leave EMPTY until a public dashboard exists. While empty, the site shows
 * "Local Deployment · Dashboard Preview Available" and never links to localhost.
 *
 * Can also be set at build time with a Vite env var:
 *   VITE_GRAFANA_URL=https://grafana.example.com/d/abc123/cloudops360
 */
export const GRAFANA_URL = (import.meta.env.VITE_GRAFANA_URL ?? '').trim()

/**
 * Path to a real dashboard screenshot placed in `public/`, e.g.
 * '/grafana-dashboard.png'. While empty, a placeholder is shown.
 */
export const DASHBOARD_SCREENSHOT = '/grafana-dashboard.png'

export const NAV_LINKS = [
  { label: 'Overview', href: '#overview' },
  { label: 'Architecture', href: '#architecture' },
  { label: 'Monitoring', href: '#monitoring' },
  { label: 'Incident Response', href: '#incident-response' },
  { label: 'Technology', href: '#technology' },
  { label: 'GitHub', href: '#github' },
]
