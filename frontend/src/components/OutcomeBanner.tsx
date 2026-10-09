import type { VerificationResult } from '../api/types'
import { BandIcon } from './Icons'

export function OutcomeBanner({ result }: { result: VerificationResult }) {
  const { outcome, match } = result
  return (
    <div className={`banner banner-${outcome.color}`} role="status">
      <BandIcon band={outcome.color} size={32} />
      <div>
        <div className="banner-label">{outcome.label}</div>
        <div className="banner-sub">
          {result.mode === 'manual' ? 'Manual fallback' : 'Mobile ID'} · record match {match.score}/100
          {match.insufficient_data && ' · insufficient data'}
        </div>
      </div>
    </div>
  )
}
