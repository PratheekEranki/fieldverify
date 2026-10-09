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

- [ ] **T03 Models + seed** (M) — depends T02
  - `models.py` per architecture §3 (including `channel`). `python -m app.seed`: 15 fake providers + 6 visits today.
  - Deliberate test cases: maiden-name alias, a "Robert" (for Bob), a hyphenated last name, an apartment address.
  - Demo provider from `DEMO_PROVIDER_*` in `.env` if set (ADR-0004).
  - Acceptance: (1) idempotent; (2) every SSN starts with 9; (3) every NPI is 10 digits and passes the NPI Luhn check.

- [ ] **T04 Scoring: normalization** (S) — test-first
  - Acceptance: tests pass for "O'Brien"→"obrien", "José"→"jose", "Smith Jr., MD"→"smith",
    "123 N Main St."→"123 n main street".

- [ ] **T05 Scoring: names** (S) — depends T04, test-first
  - Jaro-Winkler thresholds (spec §5), last-name aliases, `nicknames.py` (~40 pairs).
  - Acceptance: (1) Robert/Bob = match; (2) Jonson/Johnson = partial; (3) alias "Garcia" matches.

- [ ] **T06 Scoring: DOB, SSN, address** (S) — test-first
  - Acceptance: (1) 1985-03-07 vs 1985-07-03 = partial; (2) 900123456 vs 900213456 = partial; (3) every result has a
    reason string.

- [ ] **T07 Scoring: engine** (S) — depends T05, T06, test-first
  - Weights, `not_provided` renormalization, < 50 provided points → yellow cap, hard rules, bands, outcome labels
    (spec §3, both modes).
  - Acceptance: (1) all exact = 100 green; (2) DOB + SSN both wrong = red; (3) names + DOB only scores out of 55 and can
    reach green.

- [ ] **T08 Manual verify API** (M) — depends T03, T07
  - `GET /api/visits`, `GET /api/visits/{id}`, `POST /api/verify/manual`; in-memory result cache (15 min TTL);
    SSN never logged.
  - Five scripted cases in `test_api_manual.py`:
    1. All exact → green, "Record match only: not cryptographically verified"
    2. "Bob" for Robert, rest exact → green
    3. Day/month swapped DOB → yellow with the swap reason
    4. Right name, wrong DOB and SSN → red (hard rule)
    5. Last name + DOB only → yellow (insufficient data)
  - Acceptance: (1) five cases pass; (2) no response contains a full SSN.

- [ ] **T09 Audit log API** (M) — depends T08
  - `POST /api/audit` by result id + notes; `GET /api/audit` with mode/band filters; `GET /api/audit/export.csv`.
    No update or delete routes.
  - Acceptance: (1) saved row has no raw SSN/DOB; (2) CSV opens in Excel; (3) a test asserts no PUT/PATCH/DELETE route
    exists under `/api/audit`.

- [ ] **T10 Hash chain** (S) — depends T09, test-first
  - Canonical JSON (sorted keys, no whitespace); `entry_hash = sha256(prev_hash + json)`; genesis `"0"*64`;
    `GET /api/audit/verify-chain`.
  - Acceptance: (1) a test that edits a stored field directly in SQLite makes verification fail at that row.

- [ ] **T11 Web UI: visits, manual verify, result, audit log** (M) — depends T08–T10
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

**Checkpoint A**: on localhost, pick a visit → manual verify → result → saved → shows in the audit log → chain OK.

---

## Phase 2 — Digital web path (Sat Oct 10)

- [ ] **T13 🧑 Spike: which Cloud SDK flow works with the real wallet ID** (M) — depends T12b
  - **First:** the only profile on our Cloud license is the portal default "Age Check Profile 2.0", which probably
    requests age-over-N only. Find where profiles are managed in the portal (likely "Custom Verification") and create
    a profile requesting given name, family name, birth date (+ portrait if offered); put its ID in
    `CREDENCE_PROFILE_ID`.
  - Human: run Credence's Digital ID Playground with the wallet; note wallet app, device, browser.
  - Agent: `scripts/spike_setup.py`: `/v1/setup` + initiate the flow; human completes the wallet step once; save the
    **redacted** raw result to `backend/tests/fixtures/<flow>_result.json`.
  - Acceptance: (1) ADR-0005 filled in; (2) fixture saved; (3) architecture §9 #1, #4, #5 answered.

- [ ] **A1 🧑 Tap2iD wallet-read test** (S, 1 hour max) — human, Saturday, independent of T13
  - Use `TAP2ID_SAMPLE_APP_KEY` from `.env` (already generated for the sample's package `com.credenceid.phoneverifier`).
  - Build and install Credence's Tap2iD Android sample app (evaluation use only; we do not copy its code) on an
    Android phone (Android 10+, NFC). Tap the wallet ID.
  - Acceptance: write the result into architecture §9 #6. **Pass = Phase 4 is possible. Fail = no Android.**

- [ ] **T14 Credence client** (S) — depends T12b
  - `credence/client.py`: setup, cached token, refresh at < 60 s, re-setup on refresh failure, Origin header.
    Tests with `httpx.MockTransport`.
  - Acceptance: (1) `/api/health` shows `credence: ok` with real creds; (2) refresh path tested.

- [ ] **T15 Digital verify API (flow from T13)** (M) — depends T13, T14, T07
  - Endpoints per architecture §4; `parse.py` written against the T13 fixture; claims → scoring input; authenticity
    mapping per architecture §5.
  - Acceptance: (1) fixture test → `authenticity.status == "verified"` + a score; (2) cancelled/denied fixture → clean
    error code, not a 500.

- [ ] **T16 🧑 Web wallet flow** (M) — depends T15
  - `wallet/dcapi.ts` or `QrPanel` + `polling.ts`, depending on the flow. Human presents the real wallet ID.
  - Acceptance: (1) real wallet → green "Verified: cryptographic + record match", 3× in a row.

- [ ] **T17 Digital error paths** (S) — depends T16
  - Cancel, deny, 90 s timeout, SDK/network error, unsupported browser → plain message + "Use manual fallback" on the
    same visit. Add each real problem hit so far to `docs/customer/troubleshooting.md`.
  - Acceptance: (1) each path checked once and listed in the commit message.

**Checkpoint B**: real wallet ID → verified result in the web app.

---

## Phase 3 — Hosting, P1 features, polish → web FEATURE FREEZE (Sun Oct 11 – Mon Oct 12)

- [ ] **T18 Full app on Render** (M) — depends T16
  - FastAPI serves `frontend/dist` when `SERVE_FRONTEND=true`; Render build command builds the frontend then installs
    the backend; secrets set as Render environment variables (never in the repo).
  - Acceptance: (1) full demo (spec §1) on the HTTPS URL; (2) `grep -r "CS-" frontend/dist` is empty.

- [ ] **T19 License barcode scan (PDF417)** (M) — depends T11
  - Camera scan of the AAMVA barcode on a US license → pre-fill the manual form. Try `@zxing/browser` first on a real
    license; answer architecture §9 #8.
  - Acceptance: (1) scanning the candidate's own license fills name, DOB, address; (2) the scan never leaves the browser
    except as the normal manual-verify request.

- [ ] **T20 Portrait on result** (S) — only if T13 showed the portrait claim is available
  - Acceptance: (1) portrait shows for digital results; (2) not in DB, CSV, or logs.

- [ ] **T21 Customer integration guide** (M)
  - `docs/customer/integration-guide.md` per spec F10.
  - Acceptance: (1) someone could configure keys, domain, and browser requirements from it without asking.

**Checkpoint C (Sun night)**: T18 done, full demo runs on the HTTPS URL.

- [ ] **T22 UI polish** (M): loading/empty states, spacing, icon + text with every color, tablet check.

- [ ] **T23 README** (M): headline, what it does, screenshots, architecture diagram, quickstart (PowerShell), env table,
  security decisions, out of scope, **How this was built** (AI tools used and for what; honest).

- [ ] **T24 Demo hardening** (S): `python -m app.seed --demo-reset`; `_private/demo-checklist.md` (steps and expected
  screens only, no narration); five clean runs on the HTTPS URL.

- [ ] **A2-backend Tap2iD endpoint** (S) — only if A1 passed; Monday
  - `POST /api/verify/digital/tap2id` with `X-Device-Token`; recomputes authenticity from the five booleans
    (architecture §5b); `channel = android`. Test with a hand-written fixture.
  - Acceptance: (1) missing/wrong token → 401; (2) all-true booleans + matching claims → green verified result.

**Checkpoint D (Mon night)**: web demo complete on HTTPS. **Web feature freeze.**

---

## Phase 4 — Android reader (Tue Oct 13, only if A1 passed). HARD STOP 8:00 PM CT.

- [ ] **A2 Android scaffold + SDK init** (M)
  - New Android Studio project `com.fieldverify.reader`, **Java**, minSdk 29, **Gradle JDK 17**; add the Kotlin
    Android plugin + `kotlinx-coroutines-android` for the one wrapper file; Credence Maven repo + dependency
    (architecture §5b); key, backend URL, device token in `local.properties` (gitignored).
  - `Tap2iDVerifier.kt` + `Tap2iDCallback.java`: the only Kotlin in the project.
  - Resolve the `SdkConfig` signature from the real artifact; answer architecture §9 #7.
  - Acceptance: (1) app launches and `initSdk` reports success on the phone.

- [ ] **A3 Visit picker + tap verify** (M) — depends A2
  - Fetch today's visits from the backend; select one; `verifyMdoc` with NFC (and QR if quick); log one redacted
    `MdocAttributes` result before writing the claim mapping.
  - Acceptance: (1) tapping the wallet ID produces a `VerificationResult` on the phone.

- [ ] **A4 Post to backend + result + save** (M) — depends A3, A2-backend
  - Post claims + booleans; render the returned outcome, authenticity, and match table; "Save" → `POST /api/audit`.
  - Acceptance: (1) the row appears in the web audit log with `channel = android`.

- [ ] **A5 🧑 Go/no-go** (S): three clean end-to-end runs before 8:00 PM CT. Pass → include in README and demo.
  Fail → remove from README and demo; it's a "phase 2" slide.

---

## Phase 5 — Deliverables (Wed Oct 14 – Thu Oct 15)

- [ ] **T25 Final verification** (S): walk `spec.md` §8 line by line; fix or document every miss. Bug fixes only.
- [ ] 🧑 Deck, in own words (drafting from Sunday; finish Wednesday)
- [ ] 🧑 Video ≤ 5 min, on camera for part of it, shows the app working; check it opens without login (Wed)
- [ ] 🧑 Email bella@credenceid.com, subject `Solution Engineer Assignment - Pratheek Eranki`, with deck, video link,
      code link; mention AI-assisted build (Thu, before 11:00 AM CT)

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
