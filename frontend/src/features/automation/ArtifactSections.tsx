import { useState, type ChangeEvent } from 'react'
import type { ArtifactField, ArtifactSection } from './types'
import {
  INSURANCE_TYPES,
  YES_NO_OPTIONS,
  addKindLabel,
  createRepeatableFields,
  groupRepeatableFields,
  sectionCountLabel,
} from './intakeRecords'
import { intakeEditKey, isMultilineIntakeField } from './overlayIntakeDetail'
import './ArtifactSections.css'

export function ArtifactFieldInput({
  label,
  value,
  disabled = false,
  multiline = false,
  onChange,
}: {
  label: string
  value: string
  disabled?: boolean
  multiline?: boolean
  onChange?: (value: string) => void
}) {
  const shared = {
    className: 'artifact-section__field-input',
    'aria-label': label,
    value,
    disabled,
    onChange: (
      event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => onChange?.(event.target.value),
  }
  if (multiline) {
    return <textarea rows={3} {...shared} />
  }
  return <input type="text" {...shared} />
}

export function ArtifactSections({
  sections,
  artifactId,
  density = 'default',
  editable = false,
  disabled = false,
  onFieldChange,
  onSectionRowsChange,
}: {
  sections: ArtifactSection[]
  artifactId: string
  density?: 'default' | 'feed'
  editable?: boolean
  disabled?: boolean
  onFieldChange?: (key: string, value: string) => void
  onSectionRowsChange?: (sectionId: string, rows: ArtifactField[]) => void
}) {
  return (
    <div
      className={`artifact-sections${density === 'feed' ? ' is-feed' : ''}${
        editable ? ' is-editable' : ''
      }`}
    >
      {sections.map((section) => (
        <ArtifactSectionBlock
          key={section.id}
          section={section}
          artifactId={artifactId}
          editable={editable}
          disabled={disabled}
          onFieldChange={onFieldChange}
          onSectionRowsChange={onSectionRowsChange}
        />
      ))}
    </div>
  )
}

function ArtifactSectionBlock({
  section,
  artifactId,
  editable,
  disabled,
  onFieldChange,
  onSectionRowsChange,
}: {
  section: ArtifactSection
  artifactId: string
  editable: boolean
  disabled: boolean
  onFieldChange?: (key: string, value: string) => void
  onSectionRowsChange?: (sectionId: string, rows: ArtifactField[]) => void
}) {
  const [open, setOpen] = useState(section.defaultExpanded ?? false)
  const repeatable = Boolean(section.repeatable)
  const editingLists = Boolean(editable && section.repeatable)
  const { fixed, records } = groupRepeatableFields(section.fields)

  const updateRows = (rows: ArtifactField[]) => {
    onSectionRowsChange?.(section.id, rows)
  }

  const patchField = (target: ArtifactField, patch: Partial<ArtifactField>) => {
    if (repeatable) {
      updateRows(
        section.fields.map((item) =>
          item.rowId === target.rowId && item.label === target.label
            ? { ...item, ...patch }
            : item,
        ),
      )
      return
    }
    if (patch.value !== undefined) {
      onFieldChange?.(intakeEditKey(section.id, target), patch.value)
    }
  }

  const removeRecord = (rowId: string | undefined) => {
    if (!rowId) return
    updateRows(
      section.fields.filter((item) => item.fixed || item.rowId !== rowId),
    )
  }

  return (
    <section
      className={`artifact-section${repeatable ? ' is-repeatable' : ''}`}
      aria-labelledby={`${artifactId}-${section.id}`}
    >
      <button
        type="button"
        className="artifact-section__toggle"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span id={`${artifactId}-${section.id}`}>{section.title}</span>
        <span className="artifact-section__count">{sectionCountLabel(section)}</span>
      </button>
      {open ? (
        <>
          {(repeatable ? fixed : section.fields).length > 0 ? (
            <dl className="artifact-section__fields">
              {(repeatable ? fixed : section.fields).map((item, index) => (
                <FieldRow
                  key={item.rowId ?? `${section.id}-${item.label}-${index}`}
                  field={item}
                  inputLabel={item.label || section.title}
                  editable={editable}
                  disabled={disabled}
                  onPatch={(patch) => patchField(item, patch)}
                />
              ))}
            </dl>
          ) : null}
          {repeatable
            ? records.map((record, recordIndex) => {
                const rowId = record[0]?.rowId
                return (
                  <div
                    key={rowId ?? `${section.id}-record-${recordIndex}`}
                    className="artifact-section__record"
                  >
                    <div className="artifact-section__record-head">
                      <span className="artifact-section__record-title">
                        {recordTitle(section, record, recordIndex)}
                      </span>
                      {editingLists ? (
                        <button
                          type="button"
                          className="artifact-section__remove"
                          aria-label={`Remove ${section.title} ${recordIndex + 1}`}
                          disabled={disabled}
                          onClick={() => removeRecord(rowId)}
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>
                    <dl className="artifact-section__fields is-record">
                      {record.map((item) => (
                        <FieldRow
                          key={`${rowId}-${item.label}`}
                          field={item}
                          inputLabel={
                            record.length === 1
                              ? item.label || section.title
                              : `${section.title} ${recordIndex + 1} ${item.label}`
                          }
                          editable={editable}
                          disabled={disabled}
                          onPatch={(patch) => patchField(item, patch)}
                        />
                      ))}
                    </dl>
                  </div>
                )
              })
            : null}
          {editingLists ? (
            <div className="artifact-section__add-row">
              <button
                type="button"
                className="artifact-section__add"
                disabled={disabled}
                onClick={() =>
                  updateRows([
                    ...section.fields,
                    ...createRepeatableFields(section),
                  ])
                }
              >
                {addKindLabel(section.addKind)}
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}

function recordTitle(
  section: ArtifactSection,
  record: ArtifactField[],
  recordIndex: number,
): string {
  const type = record.find((item) => item.label === 'Type')?.value
  const name = record.find((item) => item.label === 'Name')?.value
  const payer = record.find((item) => item.label === 'Payer')?.value
  const code = record.find((item) => item.label === 'Code')?.value
  const heading =
    (type && type !== '—' ? type : null) ||
    (name && name !== '—' ? name : null) ||
    (payer && payer !== '—' ? payer : null) ||
    (code && code !== '—' ? code : null) ||
    record[0]?.label
  return heading || `${section.title} ${recordIndex + 1}`
}

function FieldRow({
  field,
  inputLabel,
  editable,
  disabled,
  onPatch,
}: {
  field: ArtifactField
  inputLabel: string
  editable: boolean
  disabled: boolean
  onPatch: (patch: Partial<ArtifactField>) => void
}) {
  return (
    <div className="artifact-section__field">
      <dt>
        {field.label || 'Field'}
        {field.required ? (
          <span className="artifact-section__required">Required</span>
        ) : null}
      </dt>
      <dd>
        {editable ? (
          <div className="artifact-section__field-edit">
            {field.choice === 'insurance-type' ? (
              <select
                className="artifact-section__type-select"
                aria-label={inputLabel}
                value={
                  INSURANCE_TYPES.includes(
                    field.value as (typeof INSURANCE_TYPES)[number],
                  )
                    ? field.value
                    : 'Other'
                }
                disabled={disabled}
                onChange={(event) => onPatch({ value: event.target.value })}
              >
                {INSURANCE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            ) : field.choice === 'yesno' ? (
              <select
                className="artifact-section__type-select"
                aria-label={inputLabel}
                value={field.value === 'Yes' || field.value === 'No' ? field.value : ''}
                disabled={disabled}
                onChange={(event) =>
                  onPatch({ value: event.target.value || '—' })
                }
              >
                <option value="">—</option>
                {YES_NO_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ) : (
              <ArtifactFieldInput
                label={inputLabel}
                value={field.value}
                disabled={disabled}
                multiline={isMultilineIntakeField(field.label)}
                onChange={(value) => onPatch({ value })}
              />
            )}
          </div>
        ) : (
          field.value
        )}
      </dd>
    </div>
  )
}
