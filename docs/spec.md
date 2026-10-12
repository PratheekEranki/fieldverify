# Spec — FieldVerify

Status: draft v2 (Oct 9 2026). v2 adds F9 Android front end, F10 customer docs, F7 raised to P1. Living document: update it when scope or rules change.

## 1. Objective

Give a Medicaid field auditor one screen that answers, during a site visit:
**"Is the person in front of me the enrolled provider, and how sure am I?"**,
and leaves an audit record the agency can rely on.

Success for the prototype = a live, end-to-end demo in under 5 minutes:
1. Auditor opens today's visit → provider presents a wallet ID → verified via Credence Cloud SDK → green result → logged.
2. Same visit, fallback path → typed details with one deliberate typo → yellow result with a field breakdown → logged.
3. Audit log shows both entries, the chain-integrity check passes, export to CSV works.

## 2. Users

| User | Goal |
|---|---|
| Field auditor (primary) | Verify the provider quickly on a tablet or laptop, record the outcome, move on |
| Program-integrity supervisor | Review the audit log, see which visits were cryptographic vs. manual, export it |
| Provider (indirect) | Prove who they are with minimal data shared |

## 3. Core concepts (non-negotiable)

**Two separate signals. Never merged into one number.**

| Signal | Question | Values | Source |
|---|---|---|---|
| **Authenticity** | Is the credential genuine and unaltered? | `verified` / `failed` / `not_checked` | Credence Cloud SDK checks (digital mode only) |
| **Record match** | Does the presented identity match the enrollment record? | score 0–100 + band | Our scoring engine (both modes) |

**Outcome** is derived from both:

| Mode | Authenticity | Match band | Outcome label |
|---|---|---|---|
| Digital | verified | green | **Verified: cryptographic + record match** |
| Digital | verified | yellow | **Credential genuine: record discrepancy, follow up** |
| Digital | verified | red | **Credential genuine but different person: escalate** |
| Digital | failed | any | **Credential failed verification: escalate** |
| Manual | not_checked | green | **Record match only: not cryptographically verified** |
| Manual | not_checked | yellow | **Partial record match: follow up** |
| Manual | not_checked | red | **Cannot verify: escalate, do not proceed** |

Manual mode can never show "Verified". That is the whole point (ADR-0002).

Special case (added Oct 12): digital, credential **verified**, but the Credence profile shared **no name and no DOB**
(e.g. the default "Age Check Profile 2.0") → **"Credential genuine: no name or DOB shared, compare the photo"**, yellow.
Nothing to compare is never treated as a mismatch, so it is never red.

Completing that result (ADR-0007): auditor confirms the photo, takes name + DOB from the physical ID →
`match_source = id_details`:

| Match band | Outcome label |
|---|---|
| green | **Credential genuine + photo confirmed; ID details match record** |
| yellow | **Credential genuine + photo confirmed; ID details partly match: follow up** |
| red | **Credential genuine, but ID details don't match the record: escalate** |

`match_source` on every result and audit entry: `wallet` (attested by the mobile ID), `id_details`, `manual`, `none`.

## 4. Features

Priority: **P0** = must work in the demo. **P1** = should have, makes the pitch stronger. **P2** = only if time is left.

### F1 — Visit list (P0)
- Home screen lists today's scheduled site visits from seed data: provider name, NPI, specialty, practice address, time.
- Selecting one opens the verification screen for **that provider's enrollment record** (1:1 verification, not a search
  across all providers).

### F1b — Unscheduled visit: provider lookup (P0, added Oct 9)
- "+ Unscheduled visit" on the visit list → search enrolled providers by **NPI (≥ 4 digits) or name (≥ 2 letters)**.
- Search never reads or returns DOB or SSN; digits are only ever matched against NPI. A query mixing letters and digits
  is rejected. Max 10 results.
- "Start visit" creates a visit for now (`visit_type = unscheduled`) and opens the normal verify screen. Verification
  stays 1:1 against the chosen record. The audit entry records `visit_type` (covered by the hash chain).
- Data source: our enrollment records (the stand-in for the state system). **Credence is not involved**: it verifies
  credentials, it has no provider or person database.
- Adding a provider who isn't enrolled is out of scope (enrollment belongs to the state system).

### F2 — Digital verification via Credence Cloud SDK (P0)
- Button "Verify with mobile ID".
- Backend starts a Cloud SDK session; frontend runs the wallet flow (DC API prompt, or QR for cross-device flows).
- Request **only**: given name, family name, birth date, and (P1) portrait for on-screen visual comparison. No address
  or document number unless needed. Request with intent-to-retain = false where the API supports it.
- On result: authenticity from the SDK's checks; record match from the scoring engine on the returned claims.
- Handles: user cancels, consent denied, timeout (90 s), SDK error. Each shows a clear message and offers manual mode.
- Which Cloud SDK flow (A/B/C/D) is implemented first is decided by spike T13 (whichever works with the candidate's
  real wallet ID). Others are P2.

### F3 — Manual fallback (P0)
- Form: first name, last name, date of birth, SSN (masked input), street address, ZIP.
- Required: last name, DOB. Others optional (missing fields score as `not_provided`, see §5).
- Auditor must tick "I compared the photo on the physical ID to the person present" before submitting.
  Stored as `photo_checked: true/false`.
- Submits to the scoring engine against the selected provider's record.

### F4 — Scoring engine (P0)
See §5. Pure Python, fully unit-tested, returns per-field breakdown + explanation strings.

### F5 — Result screen (P0)
- Large outcome label + color (green / yellow / red).
- Two clearly separate panels: **Authenticity** (with which checks passed, issuer) and **Record match** (score, band,
  per-field table: field, outcome, points earned / possible, reason, e.g. "Day and month swapped").
- Raw sensitive values are never displayed back in full (SSN shown as `***-**-1234`).
- Notes field + "Save to audit log" button.

### F6 — Audit log (P0 list + export; P1 hash chain)
- Append-only table: timestamp, auditor, provider, NPI, mode, authenticity, score, band, outcome, photo_checked,
  per-field outcomes, notes.
- Screen with filters (mode, band) and **Export CSV**.
- **P1 tamper-evidence:** each entry stores `prev_hash` and `entry_hash = sha256(prev_hash + canonical JSON of entry)`.
  "Verify chain" button recomputes and reports OK or the first broken entry.

### F7 — License barcode scan (P1, listed in Credence's nice-to-haves: PDF417)
- In manual mode, "Scan license barcode" uses the device camera to read the AAMVA PDF417 barcode on the back of a US
  driver's license and pre-fills name, DOB, address. The auditor still confirms the photo.
- Decoded entirely in the browser (zxing-wasm); only the parsed name, DOB, street and ZIP fill the form. The license
  number (AAMVA `DAQ`) is never read. Decoder (~1 MB WASM) loads only when the button is used.

### F8 — Auditor sign-in (P2)
- Hard-coded demo auditor is fine for P0. A name picker at P2. No real auth.

### F9 — Android reader app on Tap2iD (stretch, time-boxed; ADR-0006)
- Second front end on the **same backend**. Auditor picks today's visit, taps the provider's phone (NFC, or QR
  engagement), Tap2iD verifies on the device, the app posts claims + check booleans to
  `POST /api/verify/digital/tap2id`, and shows the returned `VerificationResult`. "Save" writes to the same audit log.
- No scoring, outcome, or audit logic in the app. Written in Java with one small Kotlin wrapper for the SDK.
- Built only if task A1 passes and the web app is frozen. Hard stop Tue Oct 13, 8:00 PM CT.

### F10 — Customer-facing integration docs (P1)
- `docs/customer/integration-guide.md`: how an agency's IT team would deploy and configure FieldVerify (keys,
  registered domain, enrollment-data connector, browser requirements).
- `docs/customer/troubleshooting.md`: real problems hit during this build, each with symptom → cause → fix.
  Written as it happens, not reconstructed at the end.

## 5. Scoring engine rules

Inputs: `presented` (fields from wallet claims or the manual form) and `record` (enrollment record).
Normalization first: lowercase, strip accents and punctuation, collapse spaces, drop name suffixes (jr, sr, ii, iii,
md, do), expand common street abbreviations (st→street, ave→avenue, rd→road, dr→drive, apt/ste removed for comparison).

| Field | Weight | Full | Partial | None |
|---|---|---|---|---|
| Last name | 20 | exact after normalization, or matches a recorded alias / maiden name | Jaro-Winkler ≥ 0.88 (typo), or matches one part of a hyphenated name → 50% | otherwise |
| First name | 10 | exact after normalization, or nickname-table equivalent (Bob ↔ Robert) | Jaro-Winkler ≥ 0.88 → 50% | otherwise |
| Date of birth | 25 | exact | day/month swapped, **or** one digit differs → 50% | otherwise |
| SSN | 30 | exact (9 digits) | one adjacent-digit transposition → 40% | otherwise |
| Address | 15 | ZIP5 equal **and** house number equal | ZIP5 equal only → 50% | otherwise |

**Missing fields** (`not_provided`, e.g. SSN is never in a wallet ID; address not requested): removed from the
denominator. Score = earned / sum(weights of provided fields) × 100.
A result with **fewer than 50 weight points provided** is capped at yellow ("insufficient data").

**Hard rules** (override the score):
- DOB `no_match` **and** SSN `no_match` → red.
- Last name `no_match` and first name `no_match` → red.

**Caps** (can only lower green to yellow):
- Fewer than 50 weight points provided ("insufficient data").
- DOB or SSN is `partial` (added Oct 9): a key-identifier discrepancy always gets a human follow-up. Without this, a
  swapped day/month with everything else exact scores 87.5 = green.

**Bands:** green ≥ 85, yellow 60–84, red < 60.

*Why exact-only for full name credit (decided Oct 9, from measured scores):* Jaro-Winkler rates Robert/Roberta 0.971
and Chen/Cheng 0.960, which are different people, while real typos (Jonson/Johnson 0.962, Smith/Smyth 0.893) land in
the same range. No threshold separates them, so a near-miss is always partial credit. "A typo never earns full credit." 

Every rule outcome carries a human-readable reason string, used on the result screen and in the pitch.

## 6. Non-functional

- Latency: manual scoring < 200 ms; digital flow bounded by the wallet (target < 15 s end to end).
- Runs locally on Windows; demo over HTTPS (required by DC API and the Credence registered domain).
- Responsive down to tablet width (auditor's device). Phone width should not break.
- Privacy: data minimization in requests; no raw SSN/DOB/portrait at rest outside the seed DB; portrait held in memory
  only for the result screen.

## 7. Out of scope (say so in the pitch if asked)

- Real integration with a state MMIS / PECOS / NPPES. Seed data stands in for the enrollment system.
- Real auditor authentication and role-based access.
- Offline mode.
- Tap2iD Verifier hardware and VDS. Tap2iD on Android only as the time-boxed F9.
- iOS app.
- Any federal SSN verification service (SSNVS / eCBSV are not available for this use case).

## 8. Acceptance (end-to-end)

- [ ] Digital path works with the candidate's real wallet ID on the demo setup, three times in a row.
- [ ] Manual path: the five scripted demo cases in `tasks/todo.md` T08 produce the expected bands.
- [ ] Wallet cancel and SDK error both show a message and offer manual mode.
- [ ] Audit log shows every saved verification; CSV export opens in Excel; chain check passes, and fails if a row is
      edited by hand in SQLite.
- [ ] No license key in the browser bundle (`grep CS- frontend/dist -r` returns nothing).
- [ ] README has quickstart, architecture diagram, and an honest "How this was built" section (AI disclosure).
- [ ] Customer integration guide and troubleshooting log exist (F10).
- [ ] *If F9 shipped:* Android tap → same result screen content → row in the same audit log with `channel = android`,
      three times in a row. If F9 didn't ship by the hard stop, no Android code is mentioned as working anywhere.
