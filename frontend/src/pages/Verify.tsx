import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { Health, Visit } from '../api/types'
import { ErrorBox, Loading } from '../components/Loading'
import { MaskedSsnInput } from '../components/MaskedSsnInput'
import { formatTime } from './VisitList'

type Form = { first_name: string; last_name: string; dob: string; ssn: string; street: string; zip5: string }
const EMPTY: Form = { first_name: '', last_name: '', dob: '', ssn: '', street: '', zip5: '' }

export function Verify() {
  const { visitId } = useParams()
  const navigate = useNavigate()
  const [visit, setVisit] = useState<Visit | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'choose' | 'manual'>('choose')
  const [form, setForm] = useState<Form>(EMPTY)
  const [photoChecked, setPhotoChecked] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    api.visit(Number(visitId)).then(setVisit).catch((e: Error) => setError(e.message))
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [visitId])

  const set = (key: keyof Form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))
  const canSubmit = form.last_name.trim() && form.dob && photoChecked && !submitting

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!visit || !canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await api.verifyManual({
        visit_id: visit.id,
        first_name: form.first_name.trim() || undefined,
        last_name: form.last_name.trim(),
        dob: form.dob,
        ssn: form.ssn || undefined,
        street: form.street.trim() || undefined,
        zip5: form.zip5.trim() || undefined,
        photo_checked: photoChecked,
      })
      // The SSN leaves the page state as soon as it has been submitted.
      setForm(EMPTY)
      navigate(`/results/${result.id}`)
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr.fields?.length ? apiErr.fields.map((f) => `${f.field}: ${f.message}`).join('; ') : apiErr.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (error && !visit) return <ErrorBox message={error} />
  if (!visit) return <Loading />

  return (
    <>
      <p className="crumb">
        <Link to="/">← Today's visits</Link>
      </p>
      <div className="page-head">
        <h1>
          {visit.provider.name}
          {visit.visit_type === 'unscheduled' && <span className="tag">Unscheduled visit</span>}
        </h1>
        <p className="muted">
          {formatTime(visit.scheduled_at)} · {visit.provider.specialty} · NPI {visit.provider.npi} ·{' '}
          {visit.site_address}
        </p>
      </div>

      {mode === 'choose' && (
        <div className="choice-grid">
          <div className="choice choice-primary">
            <h2>Verify with mobile ID</h2>
            <p>The provider presents the ID in their phone wallet. Verified cryptographically by Credence ID.</p>
            <button className="button" disabled title="Connected in the next build step">
              Verify with mobile ID
            </button>
            <p className="small muted">
              {health?.credence_configured
                ? 'Credence Cloud SDK is configured. Wallet flow coming in the next build step.'
                : 'Credence Cloud SDK not configured on this server yet.'}
            </p>
          </div>
          <div className="choice">
            <h2>Manual fallback</h2>
            <p>No mobile ID available? Type the details from the physical ID and match them against the enrollment record.</p>
            <button className="button button-secondary" onClick={() => setMode('manual')}>
              Use manual fallback
            </button>
            <p className="small muted">Result is a record match only, never "verified".</p>
          </div>
        </div>
      )}

      {mode === 'manual' && (
        <form className="panel form" onSubmit={submit} autoComplete="off">
          <h2>Manual fallback</h2>
          <p className="panel-help">
            Enter what is printed on the provider's physical ID. Required: last name and date of birth. Every extra
            field makes the match stronger.
          </p>
          <div className="form-grid">
            <label>
              First name
              <input value={form.first_name} onChange={(e) => set('first_name')(e.target.value)} />
            </label>
            <label>
              <span>
                Last name <span className="req">*</span>
              </span>
              <input value={form.last_name} onChange={(e) => set('last_name')(e.target.value)} required />
            </label>
            <label>
              <span>
                Date of birth <span className="req">*</span>
              </span>
              <input type="date" value={form.dob} onChange={(e) => set('dob')(e.target.value)} required />
            </label>
            <label htmlFor="ssn">
              SSN
              <MaskedSsnInput id="ssn" value={form.ssn} onChange={set('ssn')} />
            </label>
            <label className="span-2">
              Street address
              <input value={form.street} onChange={(e) => set('street')(e.target.value)} />
            </label>
            <label>
              ZIP code
              <input inputMode="numeric" maxLength={10} value={form.zip5} onChange={(e) => set('zip5')(e.target.value)} />
            </label>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={photoChecked} onChange={(e) => setPhotoChecked(e.target.checked)} />I
            compared the photo on the physical ID to the person present.
          </label>
          {error && <ErrorBox message={error} />}
          <div className="actions">
            <button type="button" className="button button-secondary" onClick={() => setMode('choose')}>
              Back
            </button>
            <button type="submit" className="button" disabled={!canSubmit}>
              {submitting ? 'Checking…' : 'Check against enrollment record'}
            </button>
          </div>
          <p className="small muted">The SSN is compared once on the server, never stored, and shown back only as the last 4 digits.</p>
        </form>
      )}
    </>
  )
}
