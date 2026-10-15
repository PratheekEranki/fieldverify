# Tasks — FieldVerify

Status: v2 (Oct 9 2026). Work top to bottom within a phase. One task per commit; name the task ID in the message.
Sizes: S ≈ < 1 h, M ≈ 1–3 h. Split anything bigger.
🧑 = needs the human (pause and ask). Schedule and checkpoints: `docs/plan.md`.

---

## Phase 1 — Backend + web manual path (Fri Oct 9, today)

- [x] **T01 🧑 Install tools** (S) — done: Python 3.12.10, Node 24.19.0, Git 2.49.0, JDK 21 (Temurin), Android Studio 2026.2.1
  - See "Software to install" at the bottom of this file.
  - Acceptance: (1) `python --version`, `node --version`, `npm --version`, `git --version` all print versions in a new
    PowerShell window.

- [x] **T02 Repo scaffold** (S) — depends T01. Done Oct 9 (backend health test passes; web build passes; FastAPI serves the built app).
  - Separate git repo: `git init` inside `fieldverify/`, and add `fieldverify/` to `D:\projects\.gitignore` so the
    parent repo never picks it up.
  - Backend skeleton with `GET /api/health`; `backend/requirements.txt` pinned (fastapi, uvicorn[standard], sqlmodel,
    pydantic-settings, httpx, jellyfish, python-dotenv, pytest, ruff).
  - Web: `npm create vite@latest frontend -- --template react-ts`, react-router, `/api` dev proxy to :8000.
  - Acceptance: (1) `/api/health` returns ok; (2) the Vite page calls it and shows "ok"; (3) `git status` shows no
    `.env` or `_private/`.

- [x] **T03 Models + seed** (M) — depends T02
  - `models.py` per architecture §3 (including `channel`). `python -m app.seed`: 15 fake providers + 6 visits today.
  - Deliberate test cases: maiden-name alias, a "Robert" (for Bob), a hyphenated last name, an apartment address.
  - Demo provider from `DEMO_PROVIDER_*` in `.env` if set (ADR-0004).
  - Acceptance: (1) idempotent; (2) every SSN starts with 9; (3) every NPI is 10 digits and passes the NPI Luhn check.

- [x] **T04 Scoring: normalization** (S) — test-first
  - Acceptance: tests pass for "O'Brien"→"obrien", "José"→"jose", "Smith Jr., MD"→"smith",
    "123 N Main St."→"123 n main street".

- [x] **T05 Scoring: names** (S) — depends T04, test-first
  - Jaro-Winkler thresholds (spec §5), last-name aliases, `nicknames.py` (~40 pairs).
  - Acceptance: (1) Robert/Bob = match; (2) Jonson/Johnson = partial; (3) alias "Garcia" matches.

- [x] **T06 Scoring: DOB, SSN, address** (S) — test-first
  - Acceptance: (1) 1985-03-07 vs 1985-07-03 = partial; (2) 900123456 vs 900213456 = partial; (3) every result has a
    reason string.

- [x] **T07 Scoring: engine** (S) — depends T05, T06, test-first
  - Weights, `not_provided` renormalization, < 50 provided points → yellow cap, hard rules, bands, outcome labels
    (spec §3, both modes).
  - Acceptance: (1) all exact = 100 green; (2) DOB + SSN both wrong = red; (3) names + DOB only scores out of 55 and can
    reach green.

- [x] **T08 Manual verify API** (M) — depends T03, T07
  - `GET /api/visits`, `GET /api/visits/{id}`, `POST /api/verify/manual`; in-memory result cache (15 min TTL);
    SSN never logged.
  - Five scripted cases in `test_api_manual.py`:
    1. All exact → green, "Record match only: not cryptographically verified"
    2. "Bob" for Robert, rest exact → green
    3. Day/month swapped DOB → yellow with the swap reason
    4. Right name, wrong DOB and SSN → red (hard rule)
    5. Last name + DOB only → yellow (insufficient data)
  - Acceptance: (1) five cases pass; (2) no response contains a full SSN.

- [x] **T09 Audit log API** (M) — depends T08
  - `POST /api/audit` by result id + notes; `GET /api/audit` with mode/band filters; `GET /api/audit/export.csv`.
    No update or delete routes.
  - Acceptance: (1) saved row has no raw SSN/DOB; (2) CSV opens in Excel; (3) a test asserts no PUT/PATCH/DELETE route
    exists under `/api/audit`.

- [x] **T10 Hash chain** (S) — depends T09, test-first
  - Canonical JSON (sorted keys, no whitespace); `entry_hash = sha256(prev_hash + json)`; genesis `"0"*64`;
    `GET /api/audit/verify-chain`.
  - Acceptance: (1) a test that edits a stored field directly in SQLite makes verification fail at that row.

- [x] **T11 Web UI: visits, manual verify, result, audit log** (M) — depends T08–T10
  - Pages `VisitList`, `Verify` (manual parts), `Result`, `AuditLog`. `MaskedInput` for SSN; required photo-check box;
    `OutcomeBanner`, `AuthenticityPanel` ("Not checked: manual mode"), `MatchTable`; "Verify chain" + "Export CSV".
  - Acceptance: (1) scripted case 3 shows yellow with the swap reason; (2) submit is disabled until the photo box is
    ticked; (3) usable at 768 px width.

- [x] **T12-portal** Credence account + Tap2iD Android key — done Oct 9. `TAP2ID_API_KEY` (package
  `com.fieldverify.reader`) and `TAP2ID_SAMPLE_APP_KEY` (for A1) are in `.env`. Portal rejected `localhost` for the
  Cloud SDK domain → Render (architecture §8).

- [x] **T12a 🧑 Render service to lock the hostname** (S) — done Oct 9: `https://fieldverify-avyq.onrender.com` (free plan, service `srv-db4j03k9v7es73a3q4bg`, branch `main`).
  - Human: sign up at render.com (GitHub login), create a free **Web Service** from the `fieldverify` GitHub repo.
  - Agent: `render.yaml` / start command for a placeholder `/api/health`; record the exact
    `https://<service>.onrender.com` URL in `.env` as `CREDENCE_ORIGIN`.
  - Acceptance: (1) `https://<service>.onrender.com/api/health` returns ok.

- [x] **T12b Cloud SDK key for the Render origin** (S) — key + profile ID in `.env` (Oct 9). `/v1/setup` from localhost with the Render Origin → 200 + tokens; base URL confirmed.
  - Portal → Generate License → Cloud SDK → registered domain = the Render URL → Evaluation. Capture license key +
    Profile ID into `.env` (key is shown once). Confirm the Cloud API base URL; answer architecture §9 #2.
  - Acceptance: (1) `CREDENCE_LICENSE_KEY`, `CREDENCE_PROFILE_ID`, `CREDENCE_ORIGIN` set; (2) a `/v1/setup` call from
    localhost with that Origin returns tokens.

- [x] **T11b Unscheduled visit: provider lookup** (M) — added Oct 9 at the human's request. Search by NPI/name only,
  `visit_type` on visits + audit entries (hashed), schema auto-rebuild for the demo DB. 54 tests; browser-checked.

**Checkpoint A — reached Fri Oct 9** (47 backend tests; browser flow checked at 1280 px and 768 px): on localhost, pick a visit → manual verify → result → saved → shows in the audit log → chain OK.

---

## Phase 2 — Digital web path (Sat Oct 10)

- [~] **T13 🧑 Spike: which Cloud SDK flow works with the real wallet ID** — superseded Oct 12: flows A/B/C wired and live (setup + sessions work); only Age Check Profile 2.0 is available (ADR-0007). No real wallet presentation yet: the candidate's wallet lacks an ID the profile accepts (troubleshooting.md). (M) — depends T12b
  - **First:** the only profile on our Cloud license is the portal default "Age Check Profile 2.0", which probably
    requests age-over-N only. Find where profiles are managed in the portal (likely "Custom Verification") and create
    a profile requesting given name, family name, birth date (+ portrait if offered); put its ID in
    `CREDENCE_PROFILE_ID`.
  - Human: run Credence's Digital ID Playground with the wallet; note wallet app, device, browser.
  - Agent: `scripts/spike_setup.py`: `/v1/setup` + initiate the flow; human completes the wallet step once; save the
    **redacted** raw result to `backend/tests/fixtures/<flow>_result.json`.
  - Acceptance: (1) ADR-0005 filled in; (2) fixture saved; (3) architecture §9 #1, #4, #5 answered.

- [x] **A1 🧑 Tap2iD wallet-read test** — done differently Oct 13: our own app (not the sample) read the Multipaz test wallet over NFC; see `docs/android/CONTEXT.md` §7. (S)
  - Use `TAP2ID_SAMPLE_APP_KEY` from `.env` (already generated for the sample's package `com.credenceid.phoneverifier`).
  - Build and install Credence's Tap2iD Android sample app (evaluation use only; we do not copy its code) on an
    Android phone (Android 10+, NFC). Tap the wallet ID.
  - Acceptance: write the result into architecture §9 #6. **Pass = Phase 4 is possible. Fail = no Android.**

- [x] **T14 Credence client** (S) — depends T12b
  - `credence/client.py`: setup, cached token, refresh at < 60 s, re-setup on refresh failure, Origin header.
    Tests with `httpx.MockTransport`.
  - Acceptance: (1) `/api/health` shows `credence: ok` with real creds; (2) refresh path tested.

- [x] **T15 Digital verify API (flows A, B, C built; parser written against documented shapes + live initiate fixtures — re-check against the first real wallet response in T13/T16)** (M) — depends T13, T14, T07
  - Endpoints per architecture §4; `parse.py` written against the T13 fixture; claims → scoring input; authenticity
    mapping per architecture §5.
  - Acceptance: (1) fixture test → `authenticity.status == "verified"` + a score; (2) cancelled/denied fixture → clean
    error code, not a 500.

- [~] **T16 🧑 Web wallet flow** — UI built and browser-checked with stubbed Credence responses (QR panel, polling, result with portrait). **Open: no real wallet test** (no accepted wallet ID available); pitch must not claim a real web wallet verification. (M) — depends T15
  - `wallet/dcapi.ts` or `QrPanel` + `polling.ts`, depending on the flow. Human presents the real wallet ID.
  - Acceptance: (1) real wallet → green "Verified: cryptographic + record match", 3× in a row.

- [x] **T17 Digital error paths** (cancel/deny → 409 → "Use manual fallback"; 90 s QR timeout; unsupported browser hides DC API buttons; Credence errors → 502 with code) (S) — depends T16
  - Cancel, deny, 90 s timeout, SDK/network error, unsupported browser → plain message + "Use manual fallback" on the
    same visit. Add each real problem hit so far to `docs/customer/troubleshooting.md`.
  - Acceptance: (1) each path checked once and listed in the commit message.

**Checkpoint B**: real wallet ID → verified result in the web app.

---

## Phase 3 — Hosting, P1 features, polish → web FEATURE FREEZE (Sun Oct 11 – Mon Oct 12)

- [x] **T18 Full app on Render** — done: live at https://fieldverify-avyq.onrender.com (web app + API, `SERVE_FRONTEND=true`); Oct 13 check: all 18 API paths present, no `CS-` or `.env` secret in the built bundle. (M)
  - FastAPI serves `frontend/dist` when `SERVE_FRONTEND=true`; Render build command builds the frontend then installs
    the backend; secrets set as Render environment variables (never in the repo).
  - Acceptance: (1) full demo (spec §1) on the HTTPS URL; (2) `grep -r "CS-" frontend/dist` is empty.

- [x] **T19 License barcode scan (PDF417)** — built Oct 12: zxing-wasm 3.1.4 (zxing-cpp) decodes a photo in the browser, `src/license/aamva.ts` parses it, form pre-fills; license number never read. 15 frontend tests incl. a PDF417 write→read round trip; browser-checked. Still to do: one try with the candidate's real license (worn cards / glare are harder than generated barcodes). (M) — depends T11
  - Camera scan of the AAMVA barcode on a US license → pre-fill the manual form. Try `@zxing/browser` first on a real
    license; answer architecture §9 #8.
  - Acceptance: (1) scanning the candidate's own license fills name, DOB, address; (2) the scan never leaves the browser
    except as the normal manual-verify request.

- [x] **T20 Portrait on result** — web: shows when the wallet shares it (browser-checked, stubbed); Android: real portrait shown Oct 13 (SDK Bitmap → JPEG). Not stored in DB, CSV or logs. (S)
  - Acceptance: (1) portrait shows for digital results; (2) not in DB, CSV, or logs.

- [x] **T21 Customer integration guide** (M) — `docs/customer/integration-guide.md` + `troubleshooting.md` (Oct 12)
  - `docs/customer/integration-guide.md` per spec F10.
  - Acceptance: (1) someone could configure keys, domain, and browser requirements from it without asking.

**Checkpoint C (Sun night)**: T18 done, full demo runs on the HTTPS URL.

- [x] **T22 UI polish** — done across Oct 11–12 (loading/empty states, icon + text with every colour, 768 px check); Android edge-to-edge fix Oct 12.

- [x] **T23 README** (M) — rewritten Oct 12 with screenshots; "How this was built" needs the candidate's review: headline, what it does, screenshots, architecture diagram, quickstart (PowerShell), env table,
  security decisions, out of scope, **How this was built** (AI tools used and for what; honest).

- [ ] **T24 Demo hardening** (S) — reset done (`POST /api/demo/reset`, token-guarded; `python -m app.seed` locally). Remaining: checklist + five clean runs: `python -m app.seed --demo-reset`; `_private/demo-checklist.md` (steps and expected
  screens only, no narration); five clean runs on the HTTPS URL.

- [x] **A2-backend Tap2iD endpoint** (S) — done Oct 12. `POST /api/verify/digital/tap2id`, `X-Device-Token`
  (401 wrong/missing, 503 if the server has none); authenticity recomputed from the real SDK checks
  (`docs/android/CONTEXT.md` §7); `channel = android`, `flow = tap2id`. `tests/test_verify_tap2id.py` (17 cases).

**Checkpoint D (Mon night)**: web demo complete on HTTPS. **Web feature freeze.**

---

## Phase 4 — Android reader (Tue Oct 13, only if A1 passed). HARD STOP 8:00 PM CT.

- [x] **A2–A4 code** — done Oct 12 in `android/` (see `android/README.md`). Builds clean (AGP 8.13.2, compileSdk 36),
  3 JVM unit tests pass. SDK signatures came from the real 2.0.0 artifact (`docs/android/CONTEXT.md`).
- [x] **A2 🧑 SDK init** — done Oct 12 (emulator): license valid, SDK 2.0.0, profile `Age Check Profile 2.0`.
- [x] **A3 🧑 Read a mobile ID** — done Oct 13 with the Multipaz test ID over NFC; result returned from Render (red: untrusted test issuer, expected).
- [x] **A4 🧑 Save** — done Oct 13: audit entry #1 on Render = Erika Mustermann, digital / android / tap2id, authenticity failed (untrusted test issuer), band yellow; hash chain verifies.

- [x] **A6 code: second read for name/DOB** — done Oct 13 (ADR-0008): `SecondReader.kt` (Multipaz 0.101.0),
  `POST /api/verify/digital/second-read` (+10 tests, 112 total), web labels. Builds; **not yet run on phones**.
- [x] **A6 🧑 Second read works on phones** — Oct 13: Erica Musterman → 73 yellow and Erika Mustermann →
  100 green match via second read (NFC); overall red (untrusted test issuer) both times. Still to try: QR variant, a save.
- [x] **A5 🧑 Go/no-go** — PASSED Oct 14 21:41–21:43 CT: three consecutive end-to-end runs (Tap2iD read + second read via QR/BLE + save) on Pixel 9 (Android 17) ↔ Samsung/Multipaz; audit #2 Erika 100 green, #3 Kevin O'Brien 0 red (wrong person caught), #4 Erika 100 green; overall red each time (untrusted test issuer). NFC tap flaky on these phones ("Transceive failed" / "Tag was lost"), QR reliable → record the demo with QR.
  Fail → remove from README and demo; it's a "phase 2" slide.

---

## Phase 5 — Deliverables (Wed Oct 14 – Thu Oct 15)

- [x] **T25 Final verification** (Oct 13 12:30) against `spec.md` §8:
  - ✗ **Digital path with the candidate's real wallet ID, 3×**: not met (no wallet ID the profile accepts). Web
    digital path is browser-tested with stubbed Credence only; Android is device-tested with the Multipaz test wallet.
  - ✓ Manual: five scripted cases (`test_api_manual.py`), all pass.
  - ✓ Wallet cancel / Credence error → message + manual fallback (browser check Oct 11; backend tests).
  - ✓ Audit log, CSV export, chain check + tamper/upgrade/delete detection (`test_audit.py`). 🧑 Open the CSV in Excel once.
  - ✓ No license key or `.env` secret in `frontend/dist`.
  - ✓ README: quickstart, diagram, AI disclosure (🧑 review "How this was built" in your own words).
  - ✓ Integration guide + troubleshooting (Android added Oct 13).
  - ◐ Android: tap → result → audit row with `channel = android` works (entries #1, #3 on Render); 🧑 three in a row = A5.
  - Tests: backend 112, frontend 15, Android 4; ruff clean; secret scan clean.
- [ ] 🧑 Deck, in own words (drafting from Sunday; finish Wednesday)
- [ ] 🧑 Video ≤ 5 min, on camera for part of it, shows the app working; check it opens without login (Wed)
- [ ] 🧑 Email bella@credenceid.com, subject `Solution Engineer Assignment - Pratheek Eranki`, with deck, video link,
      code link; mention AI-assisted build (Thu, before 11:00 AM CT)

- [x] **T19b Age Check profile support** (Oct 12, ADR-0007): attributes, `match_source`, `POST /api/verify/digital/supplement`,
  Complete-the-match panel; 81 backend tests; browser-checked end to end against a fake Credence returning the
  Age Check payload.

## P2 backlog (only after Checkpoint D, never on Tuesday)

- [ ] Second Cloud SDK flow (another wallet)
- [ ] Auditor name picker
- [ ] Supervisor summary view (counts by mode/band)

---

## Software to install

| When | Tool | Notes | Check |
|---|---|---|---|
| ✅ | Python 3.12.10 | installed | `python --version` |
| ✅ | Node.js 24.19.0 | installed | `node --version`, `npm --version` |
| ✅ | Git 2.49.0 | installed | `git --version` |
| ✅ | JDK 21 (Temurin) | installed; Android builds use Gradle JDK 17 instead | `java --version` |
| Today (optional) | VS Code | Probably already installed | — |
| T12a | Render account | render.com, sign in with GitHub. No local install. | Dashboard opens |
| ✅ / Saturday (A1) | Android Studio 2026.2.1 | installed; set Gradle JDK 17 per project; need an Android 10+ phone with NFC + USB debugging | Phone visible in Device Manager |
