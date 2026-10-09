import { useState } from 'react'

// SSN entry: digits only, formatted ###-##-####, hidden by default (shoulder-surfing at a site visit).
function format(digits: string): string {
  const d = digits.slice(0, 9)
  if (d.length <= 3) return d
  if (d.length <= 5) return `${d.slice(0, 3)}-${d.slice(3)}`
  return `${d.slice(0, 3)}-${d.slice(3, 5)}-${d.slice(5)}`
}

export function MaskedSsnInput({
  id,
  value,
  onChange,
}: {
  id: string
  value: string
  onChange: (digits: string) => void
}) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="ssn-input">
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        placeholder="###-##-####"
        value={format(value)}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 9))}
      />
      <button type="button" className="link-button" onClick={() => setVisible((v) => !v)}>
        {visible ? 'Hide' : 'Show'}
      </button>
    </div>
  )
}
