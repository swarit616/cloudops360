/**
 * Anchor for links that leave the site. Always opens in a new tab with
 * rel="noopener noreferrer" to prevent tab-nabbing and referrer leakage.
 */
export default function ExternalLink({ href, className = '', children, ...rest }) {
  return (
    <a
      href={href}
      className={className}
      target="_blank"
      rel="noopener noreferrer"
      {...rest}
    >
      {children}
    </a>
  )
}
