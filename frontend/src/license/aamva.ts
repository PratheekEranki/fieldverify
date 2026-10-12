// Parse the AAMVA DL/ID card PDF417 payload (the barcode on the back of US and Canadian licenses).
// Only the fields FieldVerify's manual form uses are extracted. The license number (DAQ) and physical
// descriptors are deliberately ignored: data minimization, and none of them are scored.

export type LicenseFields = {
  firstName?: string
  middleName?: string
  lastName?: string
  dob?: string // ISO YYYY-MM-DD
  street?: string
  city?: string
  state?: string
  zip5?: string
}

// AAMVA element ids we read. DCT is the older (pre-2009) combined given-name element.
const WANTED = new Set(['DCS', 'DAC', 'DCT', 'DAD', 'DBB', 'DAG', 'DAI', 'DAJ', 'DAK'])

function titleCase(s: string): string {
  return s.toLowerCase().replace(/(^|[\s'-])([a-z])/g, (_, sep: string, ch: string) => sep + ch.toUpperCase())
}

function clean(value: string): string | undefined {
  const v = value.trim()
  // "NONE" / "unavl" are AAMVA placeholders for a missing value.
  return v && !/^(none|unavl|unavail)$/i.test(v) ? v : undefined
}

export function parseAamvaDate(raw: string): string | undefined {
  const d = raw.trim()
  if (!/^\d{8}$/.test(d)) return undefined
  // US cards use MMDDCCYY; Canadian cards use CCYYMMDD.
  const [y, m, day] = /^(19|20)\d{2}(0[1-9]|1[0-2])/.test(d)
    ? [d.slice(0, 4), d.slice(4, 6), d.slice(6, 8)]
    : [d.slice(4, 8), d.slice(0, 2), d.slice(2, 4)]
  const iso = `${y}-${m}-${day}`
  const parsed = new Date(`${iso}T00:00:00Z`)
  return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== iso ? undefined : iso
}

export function looksLikeAamva(raw: string): boolean {
  const text = normalizeControls(raw)
  return /ANSI\s?\d{6}/.test(text) || /(^|[\n\r])DCS/.test(text) || /DLDAQ|IDDAQ/.test(text)
}

// zxing's human-readable text mode shows control characters as <LF>, <CR>, <RS>; turn them back.
function normalizeControls(text: string): string {
  return text.replace(/<LF>/g, '\n').replace(/<CR>/g, '\r').replace(/<RS>/g, '\x1e').replace(/<GS>/g, '\x1d')
}

export function parseAamva(raw: string): LicenseFields {
  const text = normalizeControls(raw)
  const elements = new Map<string, string>()
  for (const line of text.split(/[\n\r\x1e]+/)) {
    // Normal element line: "DCSKOWALSKI". The first element of a subfile follows the header on the same line:
    // "ANSI 636026080102DL00410288ZA03290015DLDAQD12345" -> take what follows the last "DL"/"ID" designator.
    const m = line.match(/^(D[A-Z]{2})(.*)$/) ?? line.match(/.*(?:DL|ID)(D[A-Z]{2})(.*)$/)
    if (!m) continue
    const [, code, value] = m
    if (WANTED.has(code) && !elements.has(code)) elements.set(code, value)
  }

  const get = (code: string) => {
    const v = elements.get(code)
    return v === undefined ? undefined : clean(v)
  }

  let first = get('DAC')
  let middle = get('DAD')
  if (!first && get('DCT')) {
    // Older cards: "JOHN,QUINCY" or "JOHN QUINCY" in one element.
    const [f, ...rest] = get('DCT')!.split(/[,\s]+/)
    first = f
    middle = middle ?? (rest.join(' ') || undefined)
  }
  const zip = get('DAK')?.replace(/\D/g, '')

  return {
    firstName: first && titleCase(first),
    middleName: middle && titleCase(middle),
    lastName: get('DCS') && titleCase(get('DCS')!),
    dob: get('DBB') && parseAamvaDate(get('DBB')!),
    street: get('DAG') && titleCase(get('DAG')!),
    city: get('DAI') && titleCase(get('DAI')!),
    state: get('DAJ')?.toUpperCase(),
    zip5: zip && zip.length >= 5 ? zip.slice(0, 5) : undefined,
  }
}
