import { type ChangeEvent, useRef, useState } from 'react'
import type { LicenseFields } from '../license/aamva'
import { ErrorBox } from './Loading'

// "Scan license barcode": photo of the back of a US/Canadian license, decoded on this device (see license/scan.ts).
export function LicenseScanButton({ onFields }: { onFields: (fields: LicenseFields) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function onPhoto(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-selecting the same photo
    if (!file) return
    setBusy(true)
    setNote(null)
    setError(null)
    try {
      const { scanLicenseImage } = await import('../license/scan')
      const fields = await scanLicenseImage(file)
      onFields(fields)
      setNote(`Filled from the license barcode${fields.state ? ` (${fields.state})` : ''}. Check the values against the card.`)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="scan-row">
        <button type="button" className="button button-secondary" onClick={() => input.current?.click()} disabled={busy}>
          {busy ? 'Reading barcode…' : 'Scan license barcode'}
        </button>
        <span className="small muted">
          Photograph the barcode on the back of the card. It is read on this device; the license number is never used.
        </span>
        <input
          ref={input}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={onPhoto}
          aria-label="Photo of the back of the license"
        />
      </div>
      {note && <p className="note note-green">{note}</p>}
      {error && <ErrorBox message={error} />}
    </>
  )
}
