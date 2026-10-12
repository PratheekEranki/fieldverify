// End-to-end check of the decoder: write a PDF417 barcode from a synthetic AAMVA payload, read it back with the
// same zxing-wasm reader the browser uses, then parse it.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { test } from 'node:test'
import { parseAamva } from '../src/license/aamva.ts'
import { SAMPLE } from './aamva.test.ts'

const require = createRequire(import.meta.url)

test('PDF417 round trip through zxing-wasm decodes and parses', async () => {
  const full = await import('zxing-wasm/full')
  full.prepareZXingModule({
    overrides: { wasmBinary: readFileSync(require.resolve('zxing-wasm/full/zxing_full.wasm')).buffer as ArrayBuffer },
  })
  const written = await full.writeBarcode(SAMPLE, { format: 'PDF417', scale: 3 })
  assert.ok(written.image, written.error)

  const results = await full.readBarcodes(written.image!, { formats: ['PDF417'], tryHarder: true, textMode: 'Plain' })
  assert.equal(results.length, 1)
  assert.equal(results[0].format, 'PDF417')
  const parsed = parseAamva(results[0].text)
  assert.equal(parsed.lastName, 'Kowalski')
  assert.equal(parsed.dob, '1971-04-12')
  assert.equal(parsed.zip5, '63301')
})
