// Browser side of the W3C Digital Credentials API (Chrome 141+, Safari 17.4+ on iOS).
// The browser asks the wallet on this device (or a nearby phone, via the browser's own QR hand-off),
// and returns the wallet's encrypted response. We pass that straight to our backend; we never decrypt it here.

type DigitalRequest = { protocol: string; data: unknown }

export class WalletError extends Error {
  kind: 'cancelled' | 'unsupported' | 'failed'
  constructor(kind: 'cancelled' | 'unsupported' | 'failed', message: string) {
    super(message)
    this.kind = kind
  }
}

export function digitalCredentialsSupported(): boolean {
  return typeof window !== 'undefined' && 'DigitalCredential' in window && !!navigator.credentials
}

// Protocol identifiers changed during standardization. Credence documents the left-hand names; current Chrome
// releases use the right-hand ones. We try the documented one first and fall back once.
const PROTOCOL_FALLBACKS: Record<string, string> = {
  openid4vp: 'openid4vp-v1-unsigned',
}

async function get(request: DigitalRequest): Promise<unknown> {
  // `digital` isn't in TypeScript's DOM types yet.
  const options = { mediation: 'required', digital: { requests: [request] } } as unknown as CredentialRequestOptions
  return navigator.credentials.get(options)
}

function extractData(credential: unknown): string {
  const data = (credential as { data?: unknown } | null)?.data
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    const d = data as Record<string, unknown>
    if (typeof d.response === 'string') return d.response
    if (typeof d.vp_token === 'string') return d.vp_token
    return JSON.stringify(d)
  }
  throw new WalletError('failed', 'The wallet returned no data.')
}

export async function requestFromWallet(protocol: string, requestData: unknown): Promise<string> {
  if (!digitalCredentialsSupported()) {
    throw new WalletError('unsupported', 'This browser does not support digital IDs. Use Chrome 141+ or Safari on iPhone.')
  }
  const attempts = [protocol, PROTOCOL_FALLBACKS[protocol]].filter(Boolean) as string[]
  let lastError: unknown
  for (const p of attempts) {
    try {
      const credential = await get({ protocol: p, data: requestData })
      if (!credential) throw new WalletError('cancelled', 'No ID was shared.')
      return extractData(credential)
    } catch (err) {
      lastError = err
      const name = (err as DOMException)?.name
      if (name === 'AbortError' || name === 'NotAllowedError') {
        throw new WalletError('cancelled', 'The ID request was cancelled.')
      }
      if (err instanceof WalletError) throw err
      // TypeError / NotSupportedError: probably the protocol name. Try the next one.
    }
  }
  throw new WalletError('failed', `The browser could not request the ID (${(lastError as Error)?.message ?? 'unknown error'}).`)
}
