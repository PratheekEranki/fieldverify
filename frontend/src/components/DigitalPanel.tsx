import QRCode from 'qrcode'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { Flow } from '../api/types'
import { WalletError, digitalCredentialsSupported, requestFromWallet } from '../wallet/dcapi'
import { ErrorBox } from './Loading'

const POLL_MS = 2000
const QR_TIMEOUT_S = 90

type Phase =
  | { kind: 'choose' }
  | { kind: 'waiting-wallet'; flow: Flow }
  | { kind: 'qr'; sessionId: string; walletUri: string; qrDataUrl: string; secondsLeft: number }
  | { kind: 'checking' }
  | { kind: 'error'; message: string; cancelled: boolean }

const FLOW_LABELS: Record<Flow, string> = {
  B: 'Google Wallet / Android',
  A: 'Apple Wallet / iPhone',
  C: 'Scan a QR code with the phone wallet',
}

export function DigitalPanel({ visitId, onManual }: { visitId: number; onManual: () => void }) {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>({ kind: 'choose' })
  const pollTimer = useRef<number | null>(null)
  const dcSupported = digitalCredentialsSupported()

  useEffect(() => () => stopPolling(), [])

  function stopPolling() {
    if (pollTimer.current !== null) window.clearInterval(pollTimer.current)
    pollTimer.current = null
  }

  function fail(err: unknown) {
    stopPolling()
    const cancelled =
      (err instanceof WalletError && err.kind === 'cancelled') || (err instanceof ApiError && err.code === 'wallet_cancelled')
    setPhase({ kind: 'error', message: (err as Error).message, cancelled })
  }

  async function startDcApi(flow: 'A' | 'B') {
    setPhase({ kind: 'waiting-wallet', flow })
    try {
      const started = await api.digitalStart(visitId, flow)
      const data = await requestFromWallet(started.browser.protocol!, started.browser.request)
      setPhase({ kind: 'checking' })
      const result = await api.digitalComplete(started.session_id, data)
      navigate(`/results/${result.id}`)
    } catch (err) {
      fail(err)
    }
  }

  async function startQr() {
    try {
      const started = await api.digitalStart(visitId, 'C')
      const walletUri = started.browser.wallet_uri!
      const qrDataUrl = await QRCode.toDataURL(walletUri, { margin: 1, width: 280, errorCorrectionLevel: 'M' })
      const deadline = Date.now() + QR_TIMEOUT_S * 1000
      setPhase({ kind: 'qr', sessionId: started.session_id, walletUri, qrDataUrl, secondsLeft: QR_TIMEOUT_S })
      let inFlight = false
      pollTimer.current = window.setInterval(async () => {
        const left = Math.max(0, Math.round((deadline - Date.now()) / 1000))
        if (left === 0) {
          fail(new WalletError('failed', 'No response from the wallet within 90 seconds.'))
          return
        }
        setPhase((p) => (p.kind === 'qr' ? { ...p, secondsLeft: left } : p))
        if (inFlight) return
        inFlight = true
        try {
          const status = await api.digitalStatus(started.session_id)
          if (status.status === 'done' && status.result) {
            stopPolling()
            navigate(`/results/${status.result.id}`)
          }
        } catch (err) {
          fail(err)
        } finally {
          inFlight = false
        }
      }, POLL_MS)
    } catch (err) {
      fail(err)
    }
  }

  if (phase.kind === 'waiting-wallet') {
    return (
      <div className="panel">
        <h2>Waiting for the wallet…</h2>
        <p>Ask the provider to approve the request in {FLOW_LABELS[phase.flow]}. They will see exactly which details are shared.</p>
        <p className="small muted">If nothing appears, the browser may show a QR code to scan with the phone.</p>
      </div>
    )
  }

  if (phase.kind === 'checking') {
    return (
      <div className="panel">
        <h2>Checking with Credence ID…</h2>
        <p className="muted">Verifying the credential's signatures and issuer.</p>
      </div>
    )
  }

  if (phase.kind === 'qr') {
    return (
      <div className="panel qr-panel">
        <div>
          <h2>Scan with the phone wallet</h2>
          <p>The provider opens their phone camera or wallet app and scans this code, then approves sharing.</p>
          <p className="small muted">
            Waiting… {phase.secondsLeft}s left. On the provider's own phone? <a href={phase.walletUri}>Open the wallet</a>.
          </p>
          <button
            className="button button-secondary"
            onClick={() => {
              stopPolling()
              setPhase({ kind: 'choose' })
            }}
          >
            Cancel
          </button>
        </div>
        <img src={phase.qrDataUrl} alt="QR code for the provider's wallet" width={280} height={280} />
      </div>
    )
  }

  if (phase.kind === 'error') {
    return (
      <div className="panel">
        <h2>{phase.cancelled ? 'The ID was not shared' : 'Mobile ID verification did not complete'}</h2>
        <ErrorBox message={phase.message} />
        <div className="actions">
          <button className="button button-secondary" onClick={() => setPhase({ kind: 'choose' })}>
            Try again
          </button>
          <button className="button" onClick={onManual}>
            Use manual fallback
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2>Verify with mobile ID</h2>
      <p className="panel-help">Choose how the provider will share their ID. Credence ID checks it cryptographically.</p>
      <div className="flow-buttons">
        <button className="button" onClick={() => startDcApi('B')} disabled={!dcSupported}>
          {FLOW_LABELS.B}
        </button>
        <button className="button" onClick={() => startDcApi('A')} disabled={!dcSupported}>
          {FLOW_LABELS.A}
        </button>
        <button className="button button-secondary" onClick={startQr}>
          {FLOW_LABELS.C}
        </button>
      </div>
      {!dcSupported && (
        <p className="small muted">
          This browser can't request wallet IDs directly (needs Chrome 141+ or Safari on iPhone). The QR option works
          in any browser.
        </p>
      )}
    </div>
  )
}
