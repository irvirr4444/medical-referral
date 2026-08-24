import { describe, expect, it } from 'vitest'
import { seedActionTimers } from '../features/automation/confirmationTimers'
import {
  displayPatientName,
  needsYouDigest,
  patientFirstName,
} from '../features/automation/needsYou'

describe('needs you digest', () => {
  it('formats last-name-first patient names for the overview', () => {
    expect(displayPatientName('Butler, Alva')).toBe('Alva Butler')
    expect(patientFirstName('Butler, Alva')).toBe('Alva')
    expect(displayPatientName('Frank Owens')).toBe('Frank Owens')
  })

  it('pins the showcase patients first and keeps totals in sync with the list', () => {
    const digest = needsYouDigest(seedActionTimers(1_000_000))

    expect(digest.ordered.slice(0, 4).map((timer) => timer.patientId)).toEqual([
      'frank-owens',
      'walter-grant',
      'thomas-reed',
      'butler-alva',
    ])
    // "Showing X of Y" copy relies on these matching.
    expect(digest.waitingTotal).toBe(digest.ordered.length)
    expect(digest.lateTotal).toBe(
      digest.ordered.filter((timer) => timer.status === 'overdue').length,
    )
    expect(digest.waitingTotal).toBeGreaterThan(digest.lateTotal)
  })
})
