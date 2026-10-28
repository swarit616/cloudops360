# CloudOps360 Portfolio (frontend)

Public portfolio homepage for **CloudOps360** (infrastructure monitoring) and **CloudRescue**
(incident response and tracking). Built with React 19 and Vite. It is a static site with no
backend, no API keys and no paid services.

## Local development

Requirements: Node.js 20.19+ (or 22.12+) and npm.

```bash
cd portfolio
npm install
npm run dev      # http://localhost:5173
npm run lint     # Oxlint
npm run build    # production build into dist/
npm run preview  # serve the production build locally
```

## Deploy to Cloudflare Pages (Free)

1. Push the repository to GitHub.
2. In Cloudflare: **Workers & Pages → Create → Pages → Connect to Git**, and pick the repository.
3. Use these build settings:

   | Setting                | Value            |
   | ---------------------- | ---------------- |
   | Framework preset       | Vite (or None)   |
   | Root directory         | `portfolio`      |
   | Build command          | `npm run build`  |
   | Build output directory | `dist`           |

4. Set the environment variable `NODE_VERSION` to `22` if the default build image is too old.
5. (Optional) add `VITE_GRAFANA_URL` under **Settings → Variables** once a public, read-only
   Grafana dashboard exists, then redeploy.

## Configuration

All links and optional settings live in `src/config/site.js`:

| Setting                | Purpose                                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| `GRAFANA_URL`          | Public Grafana URL, read from `VITE_GRAFANA_URL`. While empty (or not public https) the site shows "Live dashboard coming soon". Never link to localhost. |
| `DASHBOARD_SCREENSHOT` | Path to a real screenshot in `public/` (for example `/grafana-dashboard.png`). While empty, a placeholder is shown. |
| `CLOUDRESCUE_URL`      | Existing CloudRescue deployment on Render.                                                                 |
| `CLOUDOPS360_REPO`, `CLOUDRESCUE_REPO` | GitHub repositories.                                                                       |

Page copy lives in `src/data/content.js`.

## Project structure

```
src/
  main.jsx              entry point
  App.jsx               page composition
  App.css, index.css    component styles, design tokens and reset
  config/site.js        URLs and optional settings
  data/content.js       text content for sections
  hooks/useReveal.js    scroll-reveal hook (respects reduced motion)
  components/           Navbar, Hero, Projects, Architecture, Monitoring,
                        IncidentResponse, TechStack, Safety, Footer, ...
```

## Notes

- The hero illustration is decorative artwork. It does not display live metrics.
- AWS and Azure integrations are described as optional; no paid cloud resources are claimed.
- Fonts (Inter, Fraunces, JetBrains Mono) load from Google Fonts with system fallbacks.
