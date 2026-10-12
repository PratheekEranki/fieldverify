import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { VerificationResult } from '../api/types'
import { AuthenticityPanel } from '../components/AuthenticityPanel'
import { CompleteMatchPanel } from '../components/CompleteMatchPanel'
import { ErrorBox, Loading } from '../components/Loading'
import { MatchTable } from '../components/MatchTable'
import { OutcomeBanner } from '../components/OutcomeBanner'

export function Result() {
  const { resultId } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [photoConfirmed, setPhotoConfirmed] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.result(resultId!).then(setResult).catch((e: Error) => setError(e.message))
  }, [resultId])

  async function save() {
    if (!result) return
    setSaving(true)
    try {
      const needsPhoto = result.mode === 'digital' && result.photo_checked == null
      const entry = await api.saveToAudit(result.id, notes, needsPhoto ? photoConfirmed : undefined)
      navigate(`/audit?highlight=${entry.id}`)
    } catch (e) {
      setError((e as Error).message)
      setSaving(false)
    }
  }

  if (error && !result) return <ErrorBox message={error} />
  if (!result) return <Loading />

  // A genuine mobile ID that shared no name/DOB (age-check profile) can be completed with the physical ID's details.
  const canComplete =
    result.mode === 'digital' && result.authenticity.status === 'verified' && result.match_source === 'none' && !result.saved

  return (
    <>
      <p className="crumb">
        <Link to={`/visits/${result.visit_id}`}>← Back to visit</Link>
      </p>
      <div className="page-head">
        <h1>{result.provider.name}</h1>
        <p className="muted">
          NPI {result.provider.npi} · {result.provider.specialty}
        </p>
      </div>
      <OutcomeBanner result={result} />
      <div className="two-col">
        <AuthenticityPanel result={result} />
        <MatchTable result={result} />
      </div>
      {canComplete && <CompleteMatchPanel result={result} />}
      <section className="panel">
        <h3>Record this visit</h3>
        {result.mode === 'digital' && result.photo_checked == null && result.portrait_data_url && !canComplete && (
          <label className="checkbox">
            <input type="checkbox" checked={photoConfirmed} onChange={(e) => setPhotoConfirmed(e.target.checked)} />
            I compared the photo from the credential to the person present.
          </label>
        )}
        <label className="block">
          Notes for the audit log
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000}
            placeholder="e.g. Provider present, office matches enrollment address" />
        </label>
        {error && <ErrorBox message={error} />}
        <div className="actions">
          {result.saved ? (
            <Link className="button" to="/audit">
              Already saved, view audit log
            </Link>
          ) : (
            <button className="button" onClick={save} disabled={saving}>
              {saving ? 'Saving…' : canComplete ? 'Save without ID details' : 'Save to audit log'}
            </button>
          )}
        </div>
      </section>
    </>
  )
}
