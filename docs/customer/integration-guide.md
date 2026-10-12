# FieldVerify integration guide

For the IT team of a state Medicaid agency running a FieldVerify pilot. It covers what you set up in Credence ID,
how to deploy, how to connect your enrollment data, and what to check before auditors go into the field.
Known problems and fixes: [troubleshooting.md](troubleshooting.md).

## 1. What runs where

| Component | Runs on | Talks to |
|---|---|---|
| Web app (React) | Auditor's laptop or tablet browser | FieldVerify backend only |
| Backend (FastAPI) | Your server or cloud host, behind HTTPS | Credence Cloud SDK API, your enrollment data |
| Credence ID Cloud SDK | Credence | Provider's phone wallet, FieldVerify backend |
| Phone wallet | Provider's phone | Credence (encrypted presentation) |

The Credence license key lives only on the backend. Browsers never see it.

## 2. Credence ID setup

1. **Account.** Register at `verify.credenceid.com`. Access is immediate.
2. **Cloud SDK license, one per domain.** License Management → Generate License → Cloud SDK → enter the exact HTTPS
   origin auditors will use (e.g. `https://fieldverify.agency.gov`). `localhost` is not accepted. Use a separate
   license for staging. Copy the key when it's shown; it is displayed once.
3. **Profile (decides which fields are requested).** The default profiles are age-check profiles and are read-only;
   they don't share a name or date of birth. Ask Credence support for a custom profile that requests, from the mDL:
   `given_name`, `family_name`, `birth_date`, `portrait`, `issuing_authority`, with intent-to-retain = false.
   Put its ID in `CREDENCE_PROFILE_ID`. To confirm what a profile requests, see troubleshooting.md.
   FieldVerify also works with the default Age Check profile: auditors confirm the photo and complete the match
   from the physical license (results are labelled accordingly).
4. **Trust list (decides which issuers are accepted).** Trust Management → Public IACA lists the issuing authorities
   (state DMVs, Google ID pass, Samsung) your account trusts. This is a **policy decision**: e.g. accept only your own
   state plus ID pass. An ID from an issuer that isn't enabled fails the issuer check even if it is genuine.
   FieldVerify records the issuer on every audit entry.

## 3. Deploy

Any host that runs Python 3.11+ and Node 20+ and serves HTTPS. The reference deployment uses a Render web service:

- **Build:** `pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build`
- **Start:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment:**

| Variable | Value |
|---|---|
| `CREDENCE_LICENSE_KEY` | from step 2.2 (secret) |
| `CREDENCE_PROFILE_ID` | from step 2.3 |
| `CREDENCE_ORIGIN` | the exact registered origin, e.g. `https://fieldverify.agency.gov` |
| `CREDENCE_BASE_URL` | `https://credenceid.com/cloudsdk/playground` (evaluation) |
| `SERVE_FRONTEND` | `true` (one origin for the app and the API) |
| `DATABASE_URL` | defaults to SQLite; use a managed database in production |
| `DEMO_RESET_TOKEN` | leave **unset** in production (the reset route then doesn't exist) |

Check: `GET /api/health` → `credence_configured: true`, and `GET /api/credence/status` → `{"ok": true, "profile": ...}`.

## 4. Connect your enrollment data

The prototype seeds synthetic providers (`backend/app/seed.py`). The scoring engine never reads the database
directly; it receives a `RecordView` (first name, last name, former names, DOB, SSN, street, ZIP). To connect your
MMIS or provider-enrollment system:

1. Replace the seed with a read-only sync or a lookup against your system (by NPI or internal provider ID).
2. Populate the `Visit` table from your site-visit schedule.
3. Keep SSN access server-side only; FieldVerify never returns it from any API.

## 5. Auditor devices

| Path | Needs |
|---|---|
| **QR code** (works everywhere) | Any modern browser; provider's phone wallet that supports OpenID4VP (e.g. Samsung Wallet) |
| **Google Wallet** | Chrome 141+ (Android 9+ or desktop) |
| **Apple Wallet** | Safari on iOS 17.4+ (iPhone 11 or later) |
| **License barcode scan** | A camera (tablet or phone); decoding happens on the device |

Firefox and in-app web views can't use the Digital Credentials API; the QR path still works there.

## 6. Before the first field day

- [ ] Verify one real wallet ID end to end on the production origin (green result, issuer shown).
- [ ] Confirm the trust list matches your policy.
- [ ] Run "Verify chain" on the audit log; export CSV and open it in Excel.
- [ ] Train auditors on the three outcomes: **Verified** (cryptographic + record match), **Record match only**
      (manual), and **follow up / escalate**. Manual results are never "verified".

## 7. Data handling summary

| Data | Where it goes | Stored? |
|---|---|---|
| Wallet name / DOB | Credence → backend → scoring | Not stored; only per-field outcomes are logged |
| Wallet photo | Credence → backend → result screen | Memory only, 15 minutes |
| SSN (manual) | Browser → backend → scoring | Never stored or logged |
| License barcode | Decoded in the browser | Never leaves the device except as the typed form fields |
| Audit entry | Database | Yes: outcome, scores, issuer, notes, hash chain |
