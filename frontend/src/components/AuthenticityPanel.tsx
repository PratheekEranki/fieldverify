import type { VerificationResult } from '../api/types'
import { BandIcon, DashIcon } from './Icons'

const CHECK_LABELS: Record<string, string> = {
  issuer_trusted: 'Issuer is trusted',
  signature_valid: 'Credential signature valid',
  device_signed: 'Device signature valid',
  not_expired: 'Credential not expired',
}

export function AuthenticityPanel({ result }: { result: VerificationResult }) {
  const { authenticity } = result
  return (
    <section className="panel">
      <h3>Authenticity</h3>
      <p className="panel-help">Is the credential itself genuine? Only a mobile ID can prove this cryptographically.</p>
      {authenticity.status === 'not_checked' ? (
        <div className="status-line muted">
          <DashIcon /> <span>Not checked: manual mode. The physical ID was inspected by eye only.</span>
        </div>
      ) : (
        <>
          <div className={`status-line text-${authenticity.status === 'verified' ? 'green' : 'red'}`}>
            <BandIcon band={authenticity.status === 'verified' ? 'green' : 'red'} />
            <strong>{authenticity.status === 'verified' ? 'Credential verified' : 'Credential failed verification'}</strong>
          </div>
          {authenticity.issuer && <p className="small">Issuer: {authenticity.issuer}</p>}
          <ul className="checks">
            {Object.entries(authenticity.checks).map(([key, ok]) => (
              <li key={key} className={ok ? 'text-green' : 'text-red'}>
                <BandIcon band={ok ? 'green' : 'red'} size={16} /> {CHECK_LABELS[key] ?? key}
              </li>
            ))}
          </ul>
        </>
      )}
      {result.photo_checked && <p className="small">Auditor confirmed the ID photo matches the person present.</p>}
    </section>
  )
}
