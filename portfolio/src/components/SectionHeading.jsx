import Reveal from './Reveal.jsx'

export default function SectionHeading({ id, eyebrow, title, children }) {
  return (
    <Reveal className="section-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id}>{title}</h2>
      {children ? <p className="lede">{children}</p> : null}
    </Reveal>
  )
}
