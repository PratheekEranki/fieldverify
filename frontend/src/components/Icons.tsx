// Small inline icons so every status color is paired with a shape (never color alone).
type Props = { size?: number }

export function CheckIcon({ size = 20 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="11" fill="currentColor" />
      <path d="M7 12.5l3.2 3.2L17 9" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function WarnIcon({ size = 20 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2L23 21H1z" fill="currentColor" />
      <path d="M12 9v5" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="12" cy="17.5" r="1.4" fill="#fff" />
    </svg>
  )
}

export function StopIcon({ size = 20 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="11" fill="currentColor" />
      <path d="M8 8l8 8M16 8l-8 8" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  )
}

export function DashIcon({ size = 20 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M8 12h8" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  )
}

export function BandIcon({ band, size }: { band: 'green' | 'yellow' | 'red'; size?: number }) {
  if (band === 'green') return <CheckIcon size={size} />
  if (band === 'yellow') return <WarnIcon size={size} />
  return <StopIcon size={size} />
}
