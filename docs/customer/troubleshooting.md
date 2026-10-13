# FieldVerify troubleshooting log

Real problems hit while building and deploying FieldVerify on the Credence ID platform, written up the way a customer's
IT team would need them: **symptom → cause → fix**. Newest first.

---

### Wallet says "your info is not found" after scanning the QR code
- **Symptom:** the provider scans FieldVerify's QR code; the wallet opens the request, then reports it has no
  matching information. FieldVerify keeps waiting until the 90-second timeout.
- **Cause:** the wallet holds no credential of the requested type. Decoding the request object (`GET` the
  `request_uri` → ES256-signed JWT) shows the default "Age Check Profile 2.0" asks only for
  `org.iso.18013.5.1.mDL` (a state mobile driver's license) or `aamva.pdf417`. A Google Wallet **ID pass** (built from
  a passport) or other ID types don't match. Separately, Credence documents the QR / `mdoc-openid4vp://` flow for
  Samsung Wallet; Google Wallet and Apple Wallet are reached through the browser's Digital Credentials API instead.
- **Fix:** match the path to the wallet (Google Wallet → "Google Wallet / Android" in Chrome 141+; Apple Wallet →
  "Apple Wallet / iPhone" in Safari; QR for Samsung Wallet), and make sure the Credence profile includes the
  provider's document type. Profiles can add "Google ID Pass" as a document type, but only via a custom profile from
  Credence support. In the meantime, use the manual fallback with the license barcode scan.

### Mobile ID verifies, but there's no name or date of birth to match
- **Symptom:** the wallet presentation succeeds and the credential is genuine, but the record-match table is empty.
- **Cause:** the Cloud SDK license is bound to a Credence **profile**, and the profile (not the API request) decides
  which fields the wallet is asked for. The default "Age Check Profile 2.0" asks an mDL only for the issuing
  authority, the portrait and an age-over-21 answer. Default profiles are read-only, and custom profiles are created
  by Credence support.
- **Fix:** ask support@credenceid.com for a custom profile that requests `given_name`, `family_name`, `birth_date`
  and `portrait`, then put its Profile ID in `CREDENCE_PROFILE_ID`. Until then FieldVerify shows a yellow
  "Credential genuine: no name or DOB shared, compare the photo" (never a red "different person") and offers
  **Complete the record match**: confirm the photo, scan the physical license, and the details are scored against
  the record (labelled as coming from the physical ID).
- **How to check which fields a profile requests:** start a flow-B session (`POST /dcapi/openid4vp/v1/initiate`) and
  read `payload.dcql_query.credentials[].claims` in the response.

### `npm test` finds no tests on Windows
- **Symptom:** `Could not find '.../tests'` from `node --test tests/`.
- **Cause:** passing a directory to `node --test` isn't supported on all Node versions, and an unquoted `*` glob is
  expanded by `sh` on Linux but not by PowerShell or cmd.
- **Fix:** `node --test "tests/**/*.test.ts"` (quoted, so Node expands the glob itself on every OS).

### License barcode decodes, but the parser finds no fields
- **Symptom:** the PDF417 barcode is read, yet the last name and DOB come back empty.
- **Cause:** zxing-cpp's default text mode is "human-readable", which turns control characters into visible tokens
  (`<LF>`, `<RS>`, `<CR>`). AAMVA payloads are newline-delimited, so every element ran together.
- **Fix:** read with `textMode: "Plain"`; the parser also converts the tokens back, as a safety net.

### The portal won't register `localhost` as the Cloud SDK domain
- **Symptom:** "Domain must be a valid hostname (e.g. https://yourapp.com)".
- **Cause:** the license is bound to the page origin the browser reports during a Digital Credentials API request.
- **Fix:** use a real HTTPS host (FieldVerify uses a Render web service). Server-side calls set the `Origin` header
  themselves, so QR-code flows can still be developed from localhost against the real API. The in-browser wallet
  flows (A/B) only work when the page is served from the registered domain.

### `/v1/setup` returns 401 `INVALID_LICENSE_KEY` with a key that works elsewhere
- **Symptom:** the same key works against one base URL and fails against another.
- **Cause:** the docs show `https://credenceid.com/cloudsdk/playground`; Credence's React sample defaults to
  `https://credenceid.com/cloudsdkdev`. Evaluation keys issued from the portal are valid on `/cloudsdk/playground`.
- **Fix:** `CREDENCE_BASE_URL=https://credenceid.com/cloudsdk/playground`.

### Validation errors echoed the submitted SSN back
- **Symptom (found in testing):** a typo in the date field returned a 422 whose body included every submitted value.
- **Cause:** FastAPI's default validation error includes the rejected `input`.
- **Fix:** a custom handler that reports field names and reasons only. Covered by a test.

## Android reader: "Engagement failed … APDU status is: 6A82, expected 9000" (Oct 12)

- **Seen:** tapping the reader phone on the phone holding the wallet ID; fails at "Connect by NFC".
- **Meaning:** 6A82 is the ISO 7816 status "file or application not found". The reader's NFC worked and reached the
  other phone, but that phone did not answer as an ISO 18013-5 mobile ID. Usually the wallet isn't in "present ID"
  mode, or the wallet/ID type doesn't allow in-person presentation to third-party readers.
- **Not the cause:** license (init succeeded), app permissions (it got as far as NFC), backend (never called).
- **Try:** open the ID in the wallet before tapping and keep the screen unlocked; hold back-to-back for 2–3 s; use the
  QR option if the wallet can show an engagement QR; confirm which wallet and ID type is on the phone.

## Android reader: "NFC service conflict" on the provider's phone (Oct 13)

- **Seen:** Samsung notification on the wallet phone listing several NFC services (Embedded tag, the wallet app,
  X "share profile"). Reads failed intermittently.
- **Fix:** Settings → Connections → NFC and contactless payments → Other NFC services: leave only the wallet app on.
  Payments are a separate setting and aren't affected.

## Android reader: "Transceive failed" / "phones lost contact" (Oct 13)

- **Seen:** most NFC attempts in testing; NFC contact dropped mid-handshake.
- **Fix:** hold the phones back to back, still, until "Connect by NFC" is ticked; then they can be separated (data
  moves over Bluetooth). The second read retries automatically up to 5 taps. The QR option avoids NFC entirely.

## Android reader: "[CODE :216] Please provide consent" (Oct 13)

- **Seen:** the provider didn't approve in time (test wallet asks for PIN 1111 and a fingerprint).
- **Fix:** separate the phones after the NFC tick and approve with both hands; the time limit is inside the SDK and
  wallet and can't be changed from the app.

