# FieldVerify

**Provider identity verification for Medicaid site visits, built on the Credence ID Cloud SDK (web) and Tap2iD SDK
(Android).**

State Medicaid agencies must visit moderate- and high-risk providers before and after enrollment, and every enrolled
provider must allow unannounced inspections ([42 CFR 455.432](https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-455/subpart-E/section-455.432)).
At the door, an auditor needs to answer one question: *is the person in front of me the enrolled provider?*

FieldVerify answers it on a laptop or tablet browser, or on an Android phone, and leaves an audit record the agency
can rely on:

- **Mobile ID (primary).** The provider shares the ID in their phone wallet. Credence ID verifies it
  cryptographically: issuer in the trust list, signatures valid, not expired. FieldVerify then matches the shared
  name and date of birth against the provider's enrollment record.
- **Manual fallback.** No wallet ID, dead phone? The auditor scans the PDF417 barcode on the back of the physical
  license (or types the details), confirms the photo, and gets a scored **record match**, clearly labelled as *not*
  cryptographically verified.
- **Android reader (in person).** The auditor's phone reads the provider's mobile ID over NFC or QR with Credence's
  Tap2iD SDK and sends the result to the same backend. When the Credence profile shares no name or date of birth,
  an optional second read with an open-source reader can fetch them; that match is labelled as not checked by
  Credence and capped at yellow. See [Android reader](#android-reader).
- **Tamper-evident audit log.** Every outcome is chained with SHA-256. Editing or deleting any row is detected.
  Exportable to CSV.

| Visits | Mobile ID (QR) | Verified |
|---|---|---|
| ![Today's visits](docs/images/01-visits.png) | ![QR code for the provider's wallet](docs/images/06-digital-qr.png) | ![Verified result](docs/images/07-digital-result.png) |

| License barcode → manual form | Manual result (yellow: DOB swapped) | Audit log, chain verified |
|---|---|---|
| ![Barcode scan](docs/images/03-manual-scanned.png) | ![Manual result](docs/images/04-manual-result.png) | ![Audit log](docs/images/09-audit.png) |

*The verified mobile-ID screenshot uses a stubbed Credence response; all other screens are the live app.*

**Live demo:** https://fieldverify-avyq.onrender.com (free hosting, so the first load after idle takes ~50 s).
All provider data is synthetic.

## How it decides

Two signals, never merged into one number:

| Signal | Question | Source |
|---|---|---|
| **Authenticity** | Is the credential genuine and unaltered? | Credence ID (mobile ID only) |
| **Record match** | Does it match this provider's enrollment record? | FieldVerify scoring engine (both modes) |

| Field | Weight | Full credit | Partial credit |
|---|---|---|---|
| Last name | 20 | exact, or a recorded former/maiden name | typo (Jaro-Winkler ≥ 0.88), one part of a hyphenated name |
| First name | 10 | exact, or a nickname (Bob = Robert) | typo |
| Date of birth | 25 | exact | day/month swapped, or one digit off |
| SSN (manual only) | 30 | exact | two adjacent digits transposed |
| Address | 15 | ZIP + house number | ZIP only |

**Working with Credence's default Age Check profile.** That profile shares the credential's issuer, photo and an
age attestation, but no name or date of birth. FieldVerify shows the credential as genuine and asks the auditor to
confirm the photo and take name + DOB from the physical ID (barcode scan). The result says exactly that:
"Credential genuine + photo confirmed; ID details match record". The fully wallet-attested
"Verified: cryptographic + record match" appears only when the profile shares name and DOB
([ADR-0007](docs/decisions/0007-age-check-profile-completion.md)).

Fields that weren't provided are left out of the denominator. Green ≥ 85, yellow 60–84, red < 60. Rules on top:
a typo never earns full credit; any DOB or SSN discrepancy caps the result at yellow; DOB *and* SSN both wrong, or
both names wrong, is red; and **a manual result can never be labelled "Verified"**. Full rules:
[`docs/spec.md`](docs/spec.md) §3 and §5.

## Architecture

```mermaid
flowchart LR
  subgraph Auditor["Auditor laptop / tablet"]
    UI["React web app"]
  end
  W["Provider's phone wallet"]
  subgraph Backend["FastAPI backend"]
    API["REST API"] --> SC["Scoring engine"]
    API --> AU["Audit log + hash chain"]
    API --> CC["Credence client\n(key + tokens server-side)"]
    API --> DB[("Enrollment records\nSQLite, synthetic")]
  end
  subgraph Phone["Auditor Android phone"]
    AND["FieldVerify Reader\n(Tap2iD SDK)"]
  end
  UI --> API
  UI -. "QR code / Digital Credentials API" .-> W
  W -- "encrypted presentation" --> CR["Credence ID Cloud SDK"]
  CC --> CR
  AND -. "NFC / QR, then Bluetooth" .-> W
  AND -- "check results + claims\n(device token)" --> API
```

- The **Credence license key never reaches the browser**. The backend owns it and the token lifecycle; the browser
  only shows a QR code or calls `navigator.credentials.get()`.
- Credence answers "is this credential genuine, and what does it say?" FieldVerify answers "is this the enrolled
  provider?" using the agency's own records. Credence holds no provider data.
- Three wallet paths are wired: **QR / deep link** (OpenID4VP, any phone wallet), **Google Wallet** and **Apple
  Wallet** via the browser's Digital Credentials API.
- More: [`docs/architecture.md`](docs/architecture.md), decisions in [`docs/decisions/`](docs/decisions/).

## Android reader

`android/` is a second front end on the same backend ([ADR-0006](docs/decisions/0006-one-backend-two-front-ends.md)).
Java, plus two thin Kotlin files for the SDKs' coroutine APIs.

1. **Today's visits** come from the backend. The top bar shows whether the Tap2iD license check passed and which
   Credence profile it runs on.
2. **Read the ID in person**: tap phones (NFC) or scan the wallet's QR code. Data moves over Bluetooth, so the phones
   can be separated once "Connect by NFC" is ticked and the provider approves on their phone.
3. **The phone sends Tap2iD's raw checks**, not a verdict: issuer signature, device signature, digests, trust chain,
   validity, errors. The backend recomputes "genuine" from those, scores any shared name/DOB and returns the result.
   The phone authenticates with a shared device token (a prototype stand-in for Play Integrity or mTLS).
4. **Result screen**: genuine or not, the credential photo (to compare with the person), "Age over 21", the record
   match, then **Save to audit log** (channel `android`).

**Second read for name and date of birth** ([ADR-0008](docs/decisions/0008-android-second-read.md)). The Tap2iD
license runs on Credence's Age Check profile, which shares the issuer, photo and age only. The result screen can run
a second, separate read with the open-source [Multipaz](https://github.com/openwallet-foundation/multipaz) reader
(OpenWallet Foundation) to request name and DOB. The backend only accepts those details if the second read's own
signature, digest and validity checks pass and the issuer matches the first read. Tap2iD still decides "genuine",
and a second-read match is capped at yellow, because nothing proves both reads came from the same phone. The proper
fix is a Credence profile that includes name and DOB in the Tap2iD read.

**Tested on two phones** with the Multipaz Test App as the wallet (a synthetic "Erika Mustermann" license from a test
issuer). Its issuer isn't in Credence's trust list, so the overall result is correctly red. The second read scored
100 (green) against the matching record and 73 (yellow) against a misspelled one.

Setup and the verified SDK details: [`android/README.md`](android/README.md),
[`docs/android/CONTEXT.md`](docs/android/CONTEXT.md).

## Privacy and security choices

- **SSN:** masked input, compared once in memory, never logged or stored, shown back only as the last 4 digits.
  Validation errors are rewritten so they can't echo it back.
- **Audit log:** stores per-field outcomes (match / partial / no match), never raw SSN, DOB or the ID photo.
  Append-only API plus a hash chain.
- **Mobile ID:** only the fields the matching needs are requested, with intent-to-retain = false. The photo is held
  in memory for the result screen only.
- **License barcode:** decoded entirely on the device; the license number is never read.
- **Provider lookup** (unannounced visits) searches by NPI or name only. You can't find a person by their SSN or DOB.
- **Android:** the Tap2iD key and device token live in `local.properties` (gitignored) and are built into the debug
  APK, so the APK is not shared. Logs record field names and types, never values.

## Quickstart (Windows / PowerShell)

Requirements: Python 3.11+, Node.js 20+.

```powershell
git clone https://github.com/PratheekEranki/fieldverify.git; cd fieldverify
copy .env.example .env        # manual mode works with no keys; add Credence keys for mobile ID

cd backend
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000      # seeds synthetic data on first start

# second terminal
cd frontend
npm install
npm run dev                                    # http://localhost:5173
```

Tests: `cd backend; pytest -q` (112 tests), `cd frontend; npm test` (15 tests, including a PDF417 encode → decode
round trip) and `cd android; .\gradlew.bat :app:testDebugUnitTest` (4 tests, built from the Tap2iD SDK's own model
classes). Android setup: [`android/README.md`](android/README.md).

Try the manual fallback on the 9:00 visit (Robert Kowalski): DOB `1971-04-12`, SSN `900-11-2233`, first name
`Bob`. Then swap the DOB to `1971-12-04` and watch it drop to yellow with the reason.

### Environment variables

| Variable | Purpose |
|---|---|
| `CREDENCE_LICENSE_KEY`, `CREDENCE_PROFILE_ID` | Cloud SDK evaluation license + profile (Credence portal → License Management) |
| `CREDENCE_ORIGIN` | The HTTPS domain registered for that license |
| `CREDENCE_BASE_URL` | `https://credenceid.com/cloudsdk/playground` |
| `DEMO_PROVIDER_FIRST/LAST/DOB` | Seeds one provider matching *your own* wallet ID, so a live demo can verify green |
| `DEMO_RESET_TOKEN` | Enables `POST /api/demo/reset` (clears the audit log before a demo). Unset = route doesn't exist |
| `SERVE_FRONTEND` | `true` on Render: FastAPI serves the built web app from the same origin |
| `ANDROID_DEVICE_TOKEN` | Shared secret the Android app sends as `X-Device-Token`. Unset = the Android endpoints return 503 |

Deploying for an agency, profiles, trust lists and known issues: [`docs/customer/integration-guide.md`](docs/customer/integration-guide.md)
and [`docs/customer/troubleshooting.md`](docs/customer/troubleshooting.md).

## Out of scope

Real MMIS / PECOS integration (synthetic records stand in), auditor authentication, offline mode, the Tap2iD Verifier
hardware, and any federal SSN verification service (not available for this use).

## How this was built

I built FieldVerify (web app, backend and Android app) in five days for a take-home assignment. I used **Claude (Anthropic) as an AI coding agent**
throughout: it wrote most of the code and tests and drafted these docs, working from a spec, an architecture
document and a task list kept in this repo ([`CLAUDE.md`](CLAUDE.md), [`docs/`](docs/), [`tasks/todo.md`](tasks/todo.md)).
I made the product and design decisions, set up the Credence and Render accounts, reviewed the work, and tested it,
including the Android app on two phones.
Several decisions came out of testing real behaviour, not the first plan; each is written up in
[`docs/decisions/`](docs/decisions/) and the troubleshooting log.
