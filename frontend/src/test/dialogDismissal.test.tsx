import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { NetworkPanel } from '../components/NetworkPanel'
import { OverviewImpactBoard } from '../components/OverviewImpactBoard'
import { PatientJourneyPanel } from '../components/PatientJourneyPanel'
import { ReferralWorkspace } from '../components/ReferralWorkspace'
import { DemoProvider } from '../state/DemoContext'
import { useDemo } from '../state/useDemo'

function ReferralWorkspaceHarness() {
  const { state, dispatch } = useDemo()

  return (
    <>
      <button
        type="button"
        onClick={() =>
          dispatch({ type: 'SELECT_REFERRAL', id: state.referrals[0].id })
        }
      >
        Open referral workspace
      </button>
      <ReferralWorkspace />
    </>
  )
}

describe('dialog Escape dismissal', () => {
  it('closes metric and date dialogs', async () => {
    const user = userEvent.setup()
    render(<OverviewImpactBoard />)

    await user.click(
      screen.getByRole('button', { name: /View patients for New referrals/i }),
    )
    expect(screen.getByRole('dialog', { name: /New referrals/i })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(
      screen.queryByRole('dialog', { name: /New referrals/i }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Reporting period/i }))
    await user.click(screen.getByRole('option', { name: /Pick dates/i }))
    expect(
      screen.getByRole('dialog', { name: /Select reporting period/i }),
    ).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(
      screen.queryByRole('dialog', { name: /Select reporting period/i }),
    ).not.toBeInTheDocument()
  })

  it('closes the network roster', async () => {
    const user = userEvent.setup()
    render(<NetworkPanel />)

    await user.click(
      screen.getByRole('button', { name: /Open case manager roster/i }),
    )
    expect(screen.getByRole('dialog', { name: /Roster/i })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: /Roster/i })).not.toBeInTheDocument()
  })

  it('closes the patient journey picker', async () => {
    const user = userEvent.setup()
    render(
      <DemoProvider>
        <PatientJourneyPanel />
      </DemoProvider>,
    )

    await user.click(screen.getByRole('button', { name: /Choose patient/i }))
    expect(
      screen.getByRole('dialog', { name: /Choose a patient/i }),
    ).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(
      screen.queryByRole('dialog', { name: /Choose a patient/i }),
    ).not.toBeInTheDocument()
  })

  it('closes the referral workspace', async () => {
    const user = userEvent.setup()
    render(
      <DemoProvider>
        <ReferralWorkspaceHarness />
      </DemoProvider>,
    )

    await user.click(
      screen.getByRole('button', { name: /Open referral workspace/i }),
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
