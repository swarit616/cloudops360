/**
 * Decorative CSS/SVG monitoring illustration.
 * All curves are static artwork — they do NOT represent real metrics.
 */
export default function MonitoringVisual() {
  return (
    <figure className="viz glass">
      <svg
        viewBox="0 0 560 400"
        role="img"
        aria-label="Decorative illustration of a monitoring dashboard with line charts and linked services. Not live data."
      >
        <defs>
          <linearGradient id="vz-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#34d399" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="vz-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#10b981" />
            <stop offset="100%" stopColor="#a3e635" />
          </linearGradient>
        </defs>

        {/* window chrome */}
        <circle cx="26" cy="24" r="4" fill="#2b3530" />
        <circle cx="42" cy="24" r="4" fill="#2b3530" />
        <circle cx="58" cy="24" r="4" fill="#2b3530" />
        <rect x="90" y="16" width="170" height="16" rx="8" fill="#141a17" />

        {/* grid */}
        <g stroke="#1b2420" strokeWidth="1">
          {[80, 130, 180, 230].map((y) => (
            <line key={y} x1="24" x2="536" y1={y} y2={y} />
          ))}
        </g>

        {/* main chart */}
        <path
          d="M24 210 C70 190 90 150 130 160 S190 215 230 180 S300 100 340 120 S410 190 450 150 S500 110 536 125 L536 250 L24 250 Z"
          fill="url(#vz-area)"
        />
        <path
          className="viz__line"
          d="M24 210 C70 190 90 150 130 160 S190 215 230 180 S300 100 340 120 S410 190 450 150 S500 110 536 125"
          fill="none"
          stroke="url(#vz-line)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M24 225 C80 220 110 205 160 212 S250 200 300 208 S400 215 450 205 S510 200 536 204"
          fill="none"
          stroke="#3f4a44"
          strokeWidth="1.5"
          strokeDasharray="4 5"
        />

        {/* small panels */}
        {[24, 204, 384].map((x, i) => (
          <g key={x} transform={`translate(${x} 270)`}>
            <rect width="152" height="96" rx="12" fill="#101512" stroke="#1f2a25" />
            <rect x="14" y="14" width="56" height="6" rx="3" fill="#2b3530" />
            <path
              d={
                i === 0
                  ? 'M14 70 L40 52 L66 60 L92 38 L118 48 L138 30'
                  : i === 1
                    ? 'M14 56 L40 62 L66 40 L92 52 L118 34 L138 42'
                    : 'M14 66 L40 46 L66 52 L92 32 L118 44 L138 36'
              }
              fill="none"
              stroke="#34d399"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </g>
        ))}
      </svg>

      <figcaption className="viz__caption">
        Illustrative visualisation — not live data
      </figcaption>
    </figure>
  )
}
