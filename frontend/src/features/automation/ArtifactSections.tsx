import { useState } from 'react'
import type { ArtifactSection } from './types'
import './ArtifactSections.css'

export function ArtifactSections({
  sections,
  artifactId,
}: {
  sections: ArtifactSection[]
  artifactId: string
}) {
  return (
    <div className="artifact-sections">
      {sections.map((section) => (
        <ArtifactSectionBlock
          key={section.id}
          section={section}
          artifactId={artifactId}
        />
      ))}
    </div>
  )
}

function ArtifactSectionBlock({
  section,
  artifactId,
}: {
  section: ArtifactSection
  artifactId: string
}) {
  const [open, setOpen] = useState(section.defaultExpanded ?? false)

  return (
    <section className="artifact-section" aria-labelledby={`${artifactId}-${section.id}`}>
      <button
        type="button"
        className="artifact-section__toggle"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span id={`${artifactId}-${section.id}`}>{section.title}</span>
        <span className="artifact-section__count">{section.fields.length} fields</span>
      </button>
      {open ? (
        <dl className="artifact-section__fields">
          {section.fields.map((field) => (
            <div key={`${section.id}-${field.label}`} className="artifact-section__field">
              <dt>{field.label}</dt>
              <dd>{field.value}</dd>
              {field.meta ? <p className="artifact-section__meta">{field.meta}</p> : null}
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  )
}
