import { Fragment, useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { AuditEntry, ChainCheck } from '../api/types'
import { BandIcon } from '../components/Icons'
import { ErrorBox, Loading } from '../components/Loading'
import { FIELD_LABELS, ResultBadge } from '../components/MatchTable'

const MATCH_SOURCE_LABELS: Record<string, string> = {
  wallet: 'mobile ID',
  id_details: 'physical ID (after mobile ID)',
  second_read: 'second read (Android, not checked by Credence)',
  manual: 'typed / scanned',
  none: 'none shared',
}

export function AuditLog() {
  const [params] = useSearchParams()
  const highlight = Number(params.get('highlight')) || null
  const [mode, setMode] = useState('')
  const [band, setBand] = useState('')
  const [entries, setEntries] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [chain, setChain] = useState<ChainCheck | null>(null)
  const [open, setOpen] = useState<number | null>(highlight)

  const load = useCallback(() => {
    setEntries(null)
    api.audit({ mode, band }).then(setEntries).catch((e: Error) => setError(e.message))
  }, [mode, band])

  useEffect(load, [load])

  return (
    <>
      <div className="page-head">
        <h1>Audit log</h1>
        <p className="muted">Append-only and tamper-evident. Every entry is chained to the one before it with SHA-256.</p>
      </div>

      <div className="toolbar">
        <label>
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="">All</option>
            <option value="digital">Mobile ID</option>
            <option value="manual">Manual</option>
          </select>
        </label>
        <label>
          Result
          <select value={band} onChange={(e) => setBand(e.target.value)}>
            <option value="">All</option>
            <option value="green">Green</option>
            <option value="yellow">Yellow</option>
            <option value="red">Red</option>
          </select>
        </label>
        <div className="toolbar-actions">
          <button className="button button-secondary" onClick={() => api.verifyChain().then(setChain)}>
            Verify chain
          </button>
          <a className="button button-secondary" href={api.exportUrl({ mode, band })}>
            Export CSV
          </a>
        </div>
      </div>

      {chain && (
        <p className={`note ${chain.ok ? 'note-green' : 'note-red'}`} role="status">
          {chain.ok
            ? `Chain intact: ${chain.entries === 1 ? 'the 1 entry verifies' : `all ${chain.entries} entries verify`}.`
            : `Chain broken at entry #${chain.first_bad_id}. The log was changed outside FieldVerify.`}
        </p>
      )}
      {error && <ErrorBox message={error} />}
      {!entries && !error && <Loading />}
      {entries && entries.length === 0 && <p className="muted">No entries yet. Verify a provider and save the result.</p>}

      {entries && entries.length > 0 && (
        <div className="table-wrap">
          <table className="table audit-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Time</th>
                <th>Provider</th>
                <th>Mode</th>
                <th>Authenticity</th>
                <th className="num">Score</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <Fragment key={e.id}>
                  <tr
                    className={`clickable ${e.id === highlight ? 'row-highlight' : ''}`}
                    onClick={() => setOpen(open === e.id ? null : e.id)}
                  >
                    <td>{e.id}</td>
                    <td>{new Date(e.created_at + (e.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString()}</td>
                    <td>
                      {e.provider_name}
                      {e.visit_type === 'unscheduled' && <span className="tag">Unscheduled</span>}
                      <div className="small muted">NPI {e.provider_npi}</div>
                    </td>
                    <td>{e.mode === 'digital' ? `Mobile ID (${e.channel})` : 'Manual'}</td>
                    <td>{e.authenticity.replace('_', ' ')}</td>
                    <td className="num">{e.score ?? '–'}</td>
                    <td>
                      <span className={`text-${e.band} inline-icon`}>
                        <BandIcon band={e.band} size={16} /> {e.outcome}
                      </span>
                    </td>
                  </tr>
                  {open === e.id && (
                    <tr className="detail-row">
                      <td colSpan={7}>
                        <div className="detail">
                          <div>
                            {e.field_results.map((f) => (
                              <div key={f.field} className="detail-field">
                                <span>{FIELD_LABELS[f.field] ?? f.field}</span> <ResultBadge value={f.result} />
                              </div>
                            ))}
                          </div>
                          <div className="small">
                            <div>Auditor: {e.auditor}</div>
                            <div>Photo checked: {e.photo_checked == null ? 'n/a' : e.photo_checked ? 'yes' : 'no'}</div>
                            <div>Name/DOB source: {MATCH_SOURCE_LABELS[e.match_source] ?? e.match_source}</div>
                            {e.notes && <div>Notes: {e.notes}</div>}
                            <div className="mono muted">hash {e.entry_hash.slice(0, 16)}…</div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
