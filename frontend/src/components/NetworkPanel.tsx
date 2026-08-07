import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import {
  WCW_CASE_MANAGERS,
  WCW_FACILITIES,
  WCW_NETWORK,
  WCW_PROVIDERS,
} from '../data/wcw'
import './NetworkPanel.css'

type RosterTab = 'caseManagers' | 'providers' | 'facilities'

const COUNT_CARDS: Array<{
  id: RosterTab
  value: number
  label: string
  openLabel: string
}> = [
  {
    id: 'caseManagers',
    value: WCW_NETWORK.caseManagerCount,
    label: 'Case managers online',
    openLabel: 'Open case manager roster',
  },
  {
    id: 'providers',
    value: WCW_NETWORK.providerCount,
    label: 'Company providers loaded',
    openLabel: 'Open provider roster',
  },
  {
    id: 'facilities',
    value: WCW_NETWORK.facilityCount,
    label: 'DRK facilities connected',
    openLabel: 'Open facility roster',
  },
]

export function NetworkPanel() {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<RosterTab>('caseManagers')
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (tab === 'caseManagers') {
      return WCW_CASE_MANAGERS.filter((item) => !q || item.name.toLowerCase().includes(q)).slice(
        0,
        40,
      )
    }
    if (tab === 'providers') {
      return WCW_PROVIDERS.filter(
        (item) =>
          !q ||
          item.name.toLowerCase().includes(q) ||
          item.city.toLowerCase().includes(q),
      ).slice(0, 40)
    }
    return WCW_FACILITIES.filter(
      (item) =>
        !q ||
        item.name.toLowerCase().includes(q) ||
        item.address.toLowerCase().includes(q),
    ).slice(0, 40)
  }, [query, tab])

  function openRoster(nextTab: RosterTab) {
    setTab(nextTab)
    setQuery('')
    setOpen(true)
  }

  return (
    <section className="network-panel panel" aria-labelledby="network-heading">
      <div className="network-panel__summary">
        <div>
          <h2 id="network-heading">WCW Network</h2>
          <p className="muted">
            Live roster counts from case managers, company providers, and DRK facilities. Select a
            count to open the roster.
          </p>
        </div>
      </div>
      <div className="network-panel__counts" aria-label="Network counts">
        {COUNT_CARDS.map((card) => (
          <button
            key={card.id}
            type="button"
            className="network-panel__count"
            aria-label={card.openLabel}
            onClick={() => openRoster(card.id)}
          >
            <strong>{card.value}</strong>
            <span>{card.label}</span>
          </button>
        ))}
      </div>

      {open ? (
        <div
          className="network-drawer-backdrop"
          role="presentation"
          onClick={() => setOpen(false)}
        >
          <aside
            className="network-drawer panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="roster-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <p className="caption">WCW Network</p>
                <h3 id="roster-title">Roster</h3>
              </div>
              <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>
                Close
              </button>
            </header>
            <div className="network-drawer__tabs" role="tablist">
              {(
                [
                  ['caseManagers', 'Case managers'],
                  ['providers', 'Providers'],
                  ['facilities', 'Facilities'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  className={tab === id ? 'is-active' : ''}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <label className="network-drawer__search">
              <Search size={16} aria-hidden="true" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search roster"
                aria-label="Search roster"
              />
            </label>
            <ul className="network-drawer__list">
              {tab === 'caseManagers'
                ? (filtered as typeof WCW_CASE_MANAGERS).map((item) => (
                    <li key={item.name}>
                      <strong>{item.name}</strong>
                      <span>{item.email ?? 'No email on file'}</span>
                    </li>
                  ))
                : null}
              {tab === 'providers'
                ? (filtered as typeof WCW_PROVIDERS).map((item) => (
                    <li key={`${item.name}-${item.npi ?? item.city}`}>
                      <strong>{item.name}</strong>
                      <span>
                        {item.city}
                        {item.npi ? ` · NPI ${item.npi}` : ''}
                      </span>
                    </li>
                  ))
                : null}
              {tab === 'facilities'
                ? (filtered as typeof WCW_FACILITIES).map((item) => (
                    <li key={`${item.name}-${item.address}`}>
                      <strong>{item.name}</strong>
                      <span>{item.address}</span>
                    </li>
                  ))
                : null}
            </ul>
          </aside>
        </div>
      ) : null}
    </section>
  )
}
