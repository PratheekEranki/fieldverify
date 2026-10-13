import type { FieldResultValue, VerificationResult } from '../api/types'
import { BandIcon, DashIcon } from './Icons'

export const FIELD_LABELS: Record<string, string> = {
  last_name: 'Last name',
  first_name: 'First name',
  dob: 'Date of birth',
  ssn: 'SSN',
  address: 'Address',
}

const RESULT_LABELS: Record<FieldResultValue, string> = {
  match: 'Match',
  partial: 'Partial',
  no_match: 'No match',
  not_provided: 'Not provided',
}

export function ResultBadge({ value }: { value: FieldResultValue }) {
  const band = value === 'match' ? 'green' : value === 'partial' ? 'yellow' : value === 'no_match' ? 'red' : null
  return (
    <span className={`badge badge-${band ?? 'muted'}`}>
      {band ? <BandIcon band={band} size={14} /> : <DashIcon size={14} />} {RESULT_LABELS[value]}
    </span>
  )
}

export function MatchTable({ result }: { result: VerificationResult }) {
  const { match } = result
  return (
    <section className="panel">
      <h3>Record match</h3>
      <p className="panel-help">
        Does the presented identity match this provider's enrollment record? Score {match.score}/100 from{' '}
        {match.provided_weight} of 100 possible weight points.
      </p>
      {result.match_source === 'id_details' && (
        <p className="note note-yellow">
          Name and date of birth were taken from the physical ID after the mobile ID was verified. The wallet's
          profile shares no name or date of birth.
        </p>
      )}
      {result.match_source === 'second_read' && (
        <p className="note note-yellow">
          Name and date of birth came from a second, separate read of the mobile ID (open-source reader), not from the
          Credence check. A match here is capped at yellow.
        </p>
      )}
      {result.match_source === 'wallet' && <p className="small muted">Name and date of birth attested by the mobile ID.</p>}
      {match.hard_rule && <p className="note note-red">Rule applied: {match.hard_rule}</p>}
      {match.provided_weight > 0 && match.caps.map((c) => (
        <p key={c} className="note note-yellow">
          Capped at yellow: {c}
        </p>
      ))}
      {match.provided_weight === 0 ? (
        <p className="muted">Nothing to compare yet: the credential shared no name or date of birth.</p>
      ) : (
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Result</th>
              <th className="num">Points</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {match.fields.map((f) => (
              <tr key={f.field}>
                <td>
                  {FIELD_LABELS[f.field] ?? f.field}
                  {f.field === 'ssn' && result.presented_ssn_masked && (
                    <div className="small muted">{result.presented_ssn_masked}</div>
                  )}
                </td>
                <td>
                  <ResultBadge value={f.result} />
                </td>
                <td className="num">{f.result === 'not_provided' ? '–' : `${f.points}/${f.max}`}</td>
                <td>{f.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </section>
  )
}
