import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { VerificationResult } from '../api/types'
import type { LicenseFields } from '../license/aamva'
import { LicenseScanButton } from './LicenseScanButton'
import { ErrorBox } from './Loading'

// Shown when a mobile ID was verified but its profile shared no name or DOB (e.g. Credence's age-check profile).
// The auditor confirms the photo, then takes name and DOB from the physical ID to complete the record match.
export function CompleteMatchPanel({ result }: { result: VerificationResult }) {
  const navigate = useNavigate()
  const [photoChecked, setPhotoChecked] = useState(false)
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [dob, setDob] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function fill(f: LicenseFields) {
    if (f.firstName) setFirst(f.firstName)
    if (f.lastName) setLast(f.lastName)
    if (f.dob) setDob(f.dob)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const completed = await api.digitalSupplement({
        result_id: result.id,
        photo_checked: photoChecked,
        first_name: first.trim() || undefined,
        last_name: last.trim(),
        dob,
      })
      navigate(`/results/${completed.id}`)
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr.fields?.length ? apiErr.fields.map((f) => `${f.field}: ${f.message}`).join('; ') : apiErr.message)
      setBusy(false)
    }
  }

  return (
    <form className="panel form complete-panel" onSubmit={submit} autoComplete="off">
      <h3>Complete the record match</h3>
      <p className="panel-help">
        The credential is genuine, but this Credence profile shares no name or date of birth. Compare the photo to the
        person, then take the name and date of birth from their physical ID.
      </p>
      <label className="checkbox">
        <input type="checkbox" checked={photoChecked} onChange={(e) => setPhotoChecked(e.target.checked)} />
        The photo from the credential matches the person present.
      </label>
      <LicenseScanButton onFields={fill} />
      <div className="form-grid">
        <label>
          First name
          <input value={first} onChange={(e) => setFirst(e.target.value)} />
        </label>
        <label>
          <span>
            Last name <span className="req">*</span>
          </span>
          <input value={last} onChange={(e) => setLast(e.target.value)} required />
        </label>
        <label>
          <span>
            Date of birth <span className="req">*</span>
          </span>
          <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} required />
        </label>
      </div>
      {error && <ErrorBox message={error} />}
      <div className="actions">
        <button type="submit" className="button" disabled={!photoChecked || !last.trim() || !dob || busy}>
          {busy ? 'Checking…' : 'Check ID details against record'}
        </button>
      </div>
    </form>
  )
}
