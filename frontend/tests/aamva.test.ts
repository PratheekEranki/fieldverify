// Run with: npm test   (Node's built-in test runner with TypeScript type stripping)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { looksLikeAamva, parseAamva, parseAamvaDate } from '../src/license/aamva.ts'

// Synthetic payload in AAMVA 2016 layout. Fake person, fake license number.
export const SAMPLE =
  '@\n\x1e\rANSI 636030090102DL00410262ZM03030007DLDAQK123456789\nDCSKOWALSKI\nDDEN\nDACROBERT\nDDFN\n' +
  'DADJAMES\nDDGN\nDCAF\nDCBNONE\nDCDNONE\nDBD01152024\nDBB04121971\nDBA04122029\nDBC1\nDAU071 IN\n' +
  'DAYBRO\nDAG214 N MAIN ST\nDAISAINT CHARLES\nDAJMO\nDAK633010000  \nDCF0123456789\nDCGUSA\n\rZMZMA01\r'

test('parses the fields the manual form uses', () => {
  assert.deepEqual(parseAamva(SAMPLE), {
    firstName: 'Robert',
    middleName: 'James',
    lastName: 'Kowalski',
    dob: '1971-04-12',
    street: '214 N Main St',
    city: 'Saint Charles',
    state: 'MO',
    zip5: '63301',
  })
})

test('never extracts the license number', () => {
  assert.ok(!JSON.stringify(parseAamva(SAMPLE)).includes('K123456789'))
})

test('first element on the header line (no newline after DL)', () => {
  const header = 'ANSI 636026080102DL00410288ZA03290015DLDCSOBRIEN\nDACKEVIN\nDBB03211980\n'
  const parsed = parseAamva(header)
  assert.equal(parsed.lastName, 'Obrien')
  assert.equal(parsed.firstName, 'Kevin')
  assert.equal(parsed.dob, '1980-03-21')
})

test('older cards with DCT given names', () => {
  const parsed = parseAamva('ANSI 636000030001DL00290153DLDCSLEE\nDCTGRACE,ANN\nDBB01291977\n')
  assert.equal(parsed.firstName, 'Grace')
  assert.equal(parsed.middleName, 'Ann')
})

test('dates: US MMDDCCYY, Canadian CCYYMMDD, invalid', () => {
  assert.equal(parseAamvaDate('04121971'), '1971-04-12')
  assert.equal(parseAamvaDate('19710412'), '1971-04-12')
  assert.equal(parseAamvaDate('13451971'), undefined)
  assert.equal(parseAamvaDate('0412197'), undefined)
})

test("accepts zxing's human-readable control tokens", () => {
  const hri = '@<LF><RS><CR>ANSI 636030090102DL00410262ZM03030007DLDAQK1<LF>DCSKOWALSKI<LF>DBB04121971<LF>'
  assert.equal(parseAamva(hri).lastName, 'Kowalski')
  assert.equal(parseAamva(hri).dob, '1971-04-12')
})

test('detects AAMVA payloads', () => {
  assert.ok(looksLikeAamva(SAMPLE))
  assert.ok(!looksLikeAamva('https://example.com'))
})
