import type { VerificationResult } from '../api/types'
import { BandIcon, DashIcon } from './Icons'

// Known Credence check names -> plain English. Unknown checks are shown with their raw name.
const CHECK_LABELS: Record<string, string> = {
  issuerTrusted: 'Issuer is in the trust list',
  issuer_trusted: 'Issuer is in the trust list',
  isIssuerVerified: 'Issuer is in the trust list',
  signatureValid: 'Credential signature valid',
  signature_valid: 'Credential signature valid',
  isIssuerSignedAuthenticated: 'Issuer signature valid',
  isDeviceSignedAuthenticated: 'Device signature valid (not copied)',
  isMsoSigned: 'Security object signed',
  vpSignatureValid: 'Presentation signature valid',
  vcSignatureValid: 'Credential signature valid',
  nonceMatches: 'Fresh response (nonce matches)',
  audienceMatches: 'Response meant for this verifier',
  notExpired: 'Credential not expired',
  credentialTypeMatches: 'Credential type as expected',
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
      {result.portrait_data_url && (
        <figure className="portrait">
          <img src={result.portrait_data_url} alt="Portrait from the mobile ID" />
          <figcaption className="small">Photo from the credential. Compare it to the person in front of you.</figcaption>
        </figure>
      )}
      {result.photo_checked && <p className="small">Auditor confirmed the ID photo matches the person present.</p>}
    </section>
  )
}
