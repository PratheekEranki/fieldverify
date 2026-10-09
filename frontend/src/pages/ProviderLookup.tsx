import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { ProviderSearchHit } from '../api/types'
import { ErrorBox } from '../components/Loading'

// Unscheduled visit: find an enrolled provider by NPI or name, then verify 1:1 against that record.
// Search never accepts personal details (DOB, SSN), so it can't be used to identify an unknown person.
export function ProviderLookup() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<ProviderSearchHit[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<number | 'search' | null>(null)

  async function search(e: FormEvent) {
    e.preventDefault()
    if (!q.trim()) return
    setBusy('search')
    setError(null)
    try {
      setHits(await api.searchProviders(q.trim()))
    } catch (err) {
      setHits(null)
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  async function start(providerId: number) {
    setBusy(providerId)
    try {
      const visit = await api.startUnscheduledVisit(providerId)
      navigate(`/visits/${visit.id}`)
    } catch (err) {
      setError((err as Error).message)
      setBusy(null)
    }
  }

  return (
    <>
      <p className="crumb">
        <Link to="/">← Today's visits</Link>
      </p>
      <div className="page-head">
        <h1>Unscheduled visit</h1>
        <p className="muted">
          Find the enrolled provider by NPI or name. Personal details like date of birth or SSN can't be searched.
        </p>
      </div>
      <form className="search-row" onSubmit={search} role="search">
        <input
          aria-label="NPI or provider name"
          placeholder="NPI (at least 4 digits) or provider name"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <button className="button" type="submit" disabled={busy === 'search' || !q.trim()}>
          {busy === 'search' ? 'Searching…' : 'Search'}
        </button>
      </form>
      {error && <ErrorBox message={error} />}
      {hits && hits.length === 0 && <p className="muted">No enrolled provider matches "{q}".</p>}
      {hits && hits.length > 0 && (
        <ul className="visit-list">
          {hits.map((h) => (
            <li key={h.provider.id} className="visit visit-hit">
              <div className="visit-main">
                <div className="visit-name">{h.provider.name}</div>
                <div className="small muted">
                  {h.provider.specialty} · NPI {h.provider.npi}
                </div>
                <div className="small">{h.practice_address}</div>
              </div>
              <div className="visit-side">
                <span className={`risk risk-${h.provider.risk_level}`}>{h.provider.risk_level} risk</span>
                <button className="button" onClick={() => start(h.provider.id)} disabled={busy !== null}>
                  {busy === h.provider.id ? 'Starting…' : 'Start visit'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
