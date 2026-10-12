// Decode the PDF417 barcode on the back of a US/Canadian license from a photo, entirely in the browser.
// This module (and the ~1 MB WebAssembly decoder) is loaded only when the auditor taps "Scan license".
// Nothing is uploaded: the decoded fields only pre-fill the manual form.
import { prepareZXingModule, readBarcodes } from 'zxing-wasm/reader'
import wasmUrl from 'zxing-wasm/reader/zxing_reader.wasm?url'
import { type LicenseFields, looksLikeAamva, parseAamva } from './aamva'

let prepared = false

function prepare() {
  if (prepared) return
  // Serve the .wasm from our own origin instead of the library's default CDN.
  prepareZXingModule({
    overrides: { locateFile: (path: string, prefix: string) => (path.endsWith('.wasm') ? wasmUrl : prefix + path) },
  })
  prepared = true
}

export class ScanError extends Error {}

export async function scanLicenseImage(image: Blob): Promise<LicenseFields> {
  prepare()
  const results = await readBarcodes(image, {
    formats: ['PDF417'],
    tryHarder: true,
    tryRotate: true,
    textMode: 'Plain',
    maxNumberOfSymbols: 1,
  })
  const text = results.find((r) => r.isValid)?.text
  if (!text) {
    throw new ScanError('No license barcode found. Photograph the back of the card, flat and filling the frame.')
  }
  if (!looksLikeAamva(text)) {
    throw new ScanError('A barcode was found, but it is not a driver license / ID card barcode.')
  }
  return parseAamva(text)
}
