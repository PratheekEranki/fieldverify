import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Visit } from '../api/types'
import { ErrorBox, Loading } from '../components/Loading'

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

export function VisitList() {
  const [visits, setVisits] = useState<Visit[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.visits().then(setVisits).catch((e: Error) => setError(e.message))
  }, [])

  const today = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })

  return (
    <>
      <div className="page-head">
        <h1>Today's site visits</h1>
        <p className="muted">{today} · Medicaid provider enrollment site visits</p>
      </div>
      {error && <ErrorBox message={error} />}
      {!visits && !error && <Loading />}
      {visits && visits.length === 0 && <p className="muted">No visits scheduled today.</p>}
      <ul className="visit-list">
        {visits?.map((v) => (
          <li key={v.id} className="visit">
            <div className="visit-time">{formatTime(v.scheduled_at)}</div>
            <div className="visit-main">
              <div className="visit-name">{v.provider.name}</div>
              <div className="small muted">
                {v.provider.specialty} · NPI {v.provider.npi}
              </div>
              <div className="small">{v.site_address}</div>
            </div>
            <div className="visit-side">
              <span className={`risk risk-${v.provider.risk_level}`}>{v.provider.risk_level} risk</span>
              <Link className="button" to={`/visits/${v.id}`}>
                Verify provider
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}
