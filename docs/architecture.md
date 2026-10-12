# Architecture — FieldVerify

Status: draft v2 (Oct 9 2026). Read `docs/spec.md` first.
v2: one shared backend with two front ends (ADR-0006).

## 1. Overview

```mermaid
flowchart LR
  subgraph Auditor laptop/tablet (Chrome 141+ / Safari 17.4+)
    UI[Web front end\nReact + TS + Cloud SDK flow]
  end
  subgraph Auditor Android phone (stretch)
    AND[Android reader\nJava + thin Kotlin wrapper + Tap2iD SDK]
  end
  subgraph Provider phone
    W[Wallet: Google / Apple / Samsung]
  end
  subgraph FieldVerify backend (FastAPI)
    API[REST API /api/*]
    CS[credence/ client\n token cache + flow calls]
    SC[scoring/ engine\n pure functions]
    AU[audit/ service\n hash chain]
    DB[(SQLite\n providers, visits, audit_log)]
  end
  CC[Credence Cloud SDK API\n credenceid.com/cloudsdk/...]

  UI -- /api --> API
  API --> CS --> CC
  API --> SC
  API --> AU --> DB
  API --> DB
  UI -- DC API prompt / QR --> W
  W -- presentation --> CC
  W -- NFC / QR tap --> AND
  AND -- claims + check results\nX-Device-Token --> API
```

Key principles:
- **The backend is the product.** Enrollment records, scoring, outcome rules, and the audit log live only there.
  Both front ends call the same API and render the same `VerificationResult`.
- **The browser never sees the Cloud SDK license key.** The backend owns the key, the token lifecycle,
  and every call that needs a bearer token. The browser only does the part that must happen on the user's page
  (the `navigator.credentials.get()` call for DC API flows, or showing a QR code).
- **Android verifies on the device.** Tap2iD runs the cryptographic checks locally; the app sends the claims and
  check booleans to the backend, which scores and logs them. See §5b for the trust model.

## 2. Repository layout

```
fieldverify/
├── CLAUDE.md                 # agent rules (read first)
├── README.md
├── .env.example              # every env var, placeholder values
├── .gitignore                # .env, _private/, *.db, .venv, node_modules, dist
├── _private/                 # gitignored: assignment context
├── docs/
│   ├── spec.md
│   ├── architecture.md
│   ├── plan.md
│   └── decisions/            # ADRs
├── tasks/
│   └── todo.md
├── scripts/
│   └── spike_setup.py        # T13 throwaway: raw /v1/setup + initiate call
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py           # FastAPI app, routers, CORS, static serving of frontend/dist in demo mode
│   │   ├── config.py         # pydantic-settings, reads .env
│   │   ├── db.py             # engine, session, create_all
│   │   ├── models.py         # SQLModel tables
│   │   ├── schemas.py        # request/response Pydantic models
│   │   ├── seed.py           # `python -m app.seed`: fake providers + today's visits
│   │   ├── routers/
│   │   │   ├── visits.py
│   │   │   ├── verify_manual.py
│   │   │   ├── verify_digital.py
│   │   │   └── audit.py
│   │   ├── scoring/
│   │   │   ├── normalize.py
│   │   │   ├── fields.py     # one function per field rule
│   │   │   ├── nicknames.py  # small nickname table
│   │   │   └── engine.py     # combine, weights, hard rules, bands, outcome
│   │   ├── credence/
│   │   │   ├── client.py     # httpx client, token cache/refresh
│   │   │   ├── flows.py      # initiate / validate per flow
│   │   │   └── parse.py      # raw response → DigitalResult
│   │   └── audit/
│   │       └── chain.py      # canonical JSON, hashing, chain verification
│   └── tests/
│       ├── test_scoring.py
│       ├── test_audit_chain.py
│       ├── test_api_manual.py
│       └── fixtures/         # recorded (redacted) Credence responses
└── frontend/
    ├── package.json
    ├── vite.config.ts        # dev proxy /api → :8000
    └── src/
        ├── main.tsx, App.tsx, routes.tsx
        ├── api/              # client.ts, types.ts
        ├── pages/            # VisitList, Verify, Result, AuditLog
        ├── components/       # OutcomeBanner, AuthenticityPanel, MatchTable, MaskedInput, QrPanel
        └── wallet/           # dcapi.ts (navigator.credentials.get wrapper), polling.ts
└── android/                  # stretch (ADR-0006); Android Studio project, Java + one Kotlin file
    ├── settings.gradle.kts   # adds the Credence Maven repo
    ├── local.properties      # gitignored: TAP2ID_API_KEY, BACKEND_URL, DEVICE_TOKEN
    └── app/src/main/java/com/fieldverify/reader/
        ├── MainActivity.java       # visit picker → tap → result (Java)
        ├── ResultActivity.java     # renders VerificationResult (Java)
        ├── BackendClient.java      # OkHttp + Gson: visits, /api/verify/digital/tap2id, /api/audit (Java)
        ├── Tap2iDCallback.java     # plain Java interface: onResult(...) / onError(...)
        └── Tap2iDVerifier.kt       # the ONLY Kotlin file: wraps suspend initSdk/verifyMdoc in a coroutine
                                    # scope and reports back through Tap2iDCallback on the main thread
```

## 3. Data model (SQLite via SQLModel)

```text
Provider            # stands in for the state enrollment record (fake data)
  id            int PK
  npi           str(10)   # fake but Luhn-valid with the 80840 prefix rule
  first_name    str
  last_name     str
  aliases       json[str] # maiden/former names
  dob           date
  ssn           str(9)    # fake, starts with 9; never returned by any API
  street        str
  city, state   str
  zip5          str(5)
  specialty     str
  risk_level    str       # limited / moderate / high

Visit
  id            int PK
  provider_id   FK Provider
  scheduled_at  datetime
  site_address  str
  status        str       # scheduled / completed
  visit_type    str       # scheduled / unscheduled

AuditEntry          # append-only; no UPDATE or DELETE route exists
  id            int PK
  created_at    datetime (UTC)
  auditor       str
  visit_id      FK Visit
  provider_id   FK Provider
  visit_type    str       # scheduled / unscheduled (hashed)
  mode          str       # digital / manual
  channel       str       # web / android
  flow          str|null  # A/B/C/D (Cloud SDK) or tap2id
  authenticity  str       # verified / failed / not_checked
  auth_checks   json      # e.g. {"issuer_trusted": true, "signature_valid": true, ...}
  issuer        str|null
  score         int|null
  band          str       # green / yellow / red
  outcome       str       # label from spec §3
  field_results json      # [{"field":"dob","result":"partial","points":12.5,"max":25,"reason":"..."}]
  photo_checked bool|null
  notes         str
  prev_hash     str(64)
  entry_hash    str(64)
```

Never stored in `AuditEntry`: presented SSN, presented DOB, portrait, full raw Credence response.

## 4. Backend API

All under `/api`. JSON. Errors use `{"error": {"code": "...", "message": "..."}}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/visits?date=today` | Today's visits with provider summary (no SSN, no DOB) |
| GET | `/api/visits/{id}` | One visit + provider summary |
| GET | `/api/providers/search?q=` | Unscheduled visits: NPI prefix (≥ 4 digits) or name words (≥ 2 letters). Never DOB/SSN |
| POST | `/api/visits/unscheduled` | Body: `provider_id`. Creates a visit for now with `visit_type = unscheduled` |
| POST | `/api/verify/manual` | Body: `visit_id`, fields, `photo_checked`. Returns `VerificationResult` (not saved yet) |
| GET | `/api/verify/results/{id}` | Re-fetch a held (unexpired) result, e.g. after a browser refresh |
| POST | `/api/verify/digital/start` | Body: `visit_id`, `flow`. Calls Credence initiate. Returns what the browser needs (DC API request payload, or QR URI + `session_id`) |
| POST | `/api/verify/digital/complete` | Body: `session_id`, plus the browser's DC API response for flows A/B. Validates with Credence, scores, returns `VerificationResult` |
| GET | `/api/verify/digital/status/{session_id}` | For QR flows C/D: polls Credence; returns `pending` or `VerificationResult` |
| POST | `/api/verify/digital/tap2id` | Android only. Header `X-Device-Token`. Body: `visit_id`, claims, Tap2iD check booleans, `issuer_info`, `validation_errors`. Returns `VerificationResult` |
| POST | `/api/audit` | Body: `VerificationResult` id + notes. Appends the chained entry |
| GET | `/api/audit?mode=&band=` | List entries |
| GET | `/api/audit/export.csv` | CSV download |
| GET | `/api/audit/verify-chain` | `{ok: true}` or `{ok: false, first_bad_id: n}` |
| GET | `/api/health` | Includes whether Credence token setup succeeded |

`VerificationResult` is held server-side in memory (dict keyed by uuid, 15-minute TTL) between verify and save, so
the client can't tamper with the score before it's logged. The portrait (if requested) lives only there.

```jsonc
// VerificationResult (response shape)
{
  "id": "uuid",
  "visit_id": 3,
  "mode": "digital",
  "channel": "web",
  "flow": "B",
  "authenticity": { "status": "verified", "checks": { "issuer_trusted": true, "signature_valid": true }, "issuer": "..." },
  "match": {
    "score": 92, "band": "green", "insufficient_data": false,
    "fields": [ { "field": "last_name", "result": "match", "points": 20, "max": 20, "reason": "Exact match" } ]
  },
  "outcome": { "label": "Verified: cryptographic + record match", "color": "green" },
  "portrait_data_url": null
}
```

## 5. Credence Cloud SDK integration

Confirmed from the public docs (Oct 9 2026):

- **Auth:** `POST {BASE}/v1/setup` with `{"licenseKey": "CS-...", "profileId": "<uuid>"}`, headers
  `Content-Type: application/json` and `Origin: <registered https domain>`. Returns `accessToken`, `refreshToken`
  (7 days), `expiresIn`. `POST /v1/refresh` rotates. Refresh when < 60 s remain; redo setup when refresh expires.
  Every call sends `Authorization: Bearer <accessToken>`.
- **Base URL:** docs list `https://credenceid.com/cloudsdk/playground`; their React sample defaults to
  `https://credenceid.com/cloudsdkdev`. → **Configurable via `CREDENCE_BASE_URL`; confirm the right one in the portal
  during T12.**
- **Flow A** (Apple Wallet, DC API + ISO mdoc): `POST /v1/getDocRequest` → `sessionId`, `dcRequest`. Browser calls
  `navigator.credentials.get({ digital: { requests: [{ protocol: "org-iso-mdoc", data: dcRequest.deviceRequest }] }, mediation: "required" })`
  (exact object shape to be confirmed in T13). Then `POST /v1/verifyDocRequest` → `res`, `resDetails` (stringified JSON, must `JSON.parse`).
- **Flow B** (Google Wallet, DC API + OpenID4VP): `POST /dcapi/openid4vp/v1/initiate` → `payload`. Browser calls DC API with
  `protocol: "openid4vp"`, `data: payload`. Then `POST /dcapi/openid4vp/v1/validate` → `res`, `resDetails`.
- **Flow C** (Samsung Wallet, OpenID4VP Annex B): `POST /openid4vp/v1/mdoc/initiate` (optional `returnUrl`) → render QR /
  deep link; poll `POST /openid4vp/v1/mdoc/result` with `sessionId`. 202 = pending; `success`, `identity`, `error`.
- **Flow D** (CA DMV app, OpenID4VP + W3C VC): `POST /w3c/openid4vp/v1/initiate` → `requestUri`, `authorizationRequest`;
  build `openid4vp://authorize?...`; poll `/w3c/openid4vp/v1/validate` ~every 2 s. Returns `claims`, `issuer`, and
  `verificationDetails` with seven checks: `vpSignatureValid`, `vcSignatureValid`, `nonceMatches`, `audienceMatches`,
  `issuerTrusted`, `notExpired`, `credentialTypeMatches`.
- **Claims seen in examples:** `given_name`, `family_name`, `birth_date`. Others (portrait, address) are requested via the
  DCQL query and **not yet confirmed** in docs.
- **Cancellation:** flows A/B return HTTP 200 with `cancelled: true`. Consent denial in C returns `success: false`.

Observed live (Oct 9, `backend/tests/fixtures/`):
- `/v1/getDocRequest` → 201 `{sessionId, dcRequest: {deviceRequest, encryptionInfo}}`.
- `/dcapi/openid4vp/v1/initiate` → 200 `{sessionId, payload}`; `payload` is the **unsigned** OpenID4VP request object
  (`response_mode: dc_api.jwt`, `dcql_query`, `client_metadata.jwks`), handed to the browser as-is.
- `/openid4vp/v1/mdoc/initiate` → 200 `{sessionId, walletUri: "mdoc-openid4vp://?client_id=credenceid.com&...",
  requestUri}`; polling `/openid4vp/v1/mdoc/result` before a scan → **202 `{"status":"pending"}`**.
- **Requested claims come from the profile, not the request.** The default "Age Check Profile 2.0" asks for
  mDL `issuing_authority` + `portrait`, or AAMVA `DCS` (last name), `DAC` (first), `DAD` (middle), `DBB` (DOB),
  `DAJ` (state). Our scoring needs `given_name`, `family_name`, `birth_date` → a custom profile is required (T13).
- **Profiles are read-only and custom ones are created by Credence support** (portal, Oct 12: "To create a new custom
  profile, please email support@credenceid.com"). "Age Check Profile 2.0" requests, for an mDL, only
  `issuing_authority`, `portrait` and the age attestation (`age_over_21`); for PDF417 it reads `DBB`. So with the
  default profile an mDL presentation yields **no name and no DOB** → handled as a yellow "compare the photo" outcome.
- AAMVA element mapping used by the parser: `DCS→family_name`, `DAC→given_name`, `DBB→birth_date`
  (US format MMDDCCYY), `DAJ→issuing state`.

Mapping to our `authenticity`:
- A/B: `res == true` → `verified`; else `failed`. Parse whatever per-check detail `resDetails` exposes into `auth_checks`.
- C: `success == true` → `verified`.
- D: `verified` only if `success` and all seven `verificationDetails` checks are true; store each check.

Mapping claims → scoring input: `given_name → first_name`, `family_name → last_name`, `birth_date → dob`
(ISO `YYYY-MM-DD`). SSN and address are `not_provided` in digital mode unless address claims are requested.

**Rule for the agent:** the first real response for each flow is logged (redacted) to `backend/tests/fixtures/` and the
parser is written against it, not against this doc.

## 5b. Credence Tap2iD SDK integration (Android stretch, ADR-0006)

Confirmed from the public docs (Oct 9 2026):

- Evaluation key: portal → License Management → Generate License → **In-person SDK** → Android → app package name
  (must match `applicationId` exactly; each package name can be registered once per account) → Evaluation (free, 90 days).
- Maven repo (in `settings.gradle.kts` → `dependencyResolutionManagement`):
  `https://nexus.credenceid.com/repository/credenceid-sdk-group/`
- Dependency: `implementation("com.credenceid:tap2idSdk:2.0.0")`
- Toolchain: Android Studio (recent), **Gradle JDK 17** (set in Settings → Build Tools → Gradle; the machine's
  default JDK 21 stays for everything else), Gradle wrapper 8.14.x, **minSdk 29 (Android 10)**.
- Language split: app code in **Java**. `initSdk` and `verifyMdoc` are Kotlin `suspend` functions, which Java can't
  call cleanly, so one Kotlin file (`Tap2iDVerifier.kt`) wraps them and exposes plain callbacks to Java. Keep all other
  logic out of that file. Needs the Kotlin Android plugin and `kotlinx-coroutines-android`.
- Entry point `Tap2iDSdk`: `initSdk(config, InitSdkResultListener)` once at startup;
  `verifyMdoc(EngagementConfig, MdocVerificationListener)` per verification. Both are `suspend`.
- `EngagementConfig(qrConfig: QrConfig?, nfcConfig: NfcConfig?)`; at least one non-null. `NfcConfig(activity)`,
  `QrConfig(mDocString)`.
- Listener stages: `onVerificationStageStarted / Error / Completed`, then `onVerificationCompleted(VerificationResult)`.
- `VerificationResult`: `mdocAttributes`, `isIssuerSignedAuthenticated`, `isDeviceSignedAuthenticated`, `issuerInfo`,
  `isIssuerVerified`, `isMsoSigned`, `validationErrors`.
- **Docs disagree** on `SdkConfig`: the integration page shows `SdkConfig(apiKey, transport = TransportType.BLE)` with
  `onSuccess/onError`; the API reference shows `SdkConfig(apiKey, applicationContext)` with
  `onInitializationSuccess/onInitializationFailure`. Resolve against the actual 2.0.0 artifact in Android Studio
  (autocomplete / decompiled class), not by guessing.
- Fields inside `MdocAttributes` are **not documented**. Log one real result (redacted) before writing the mapping.

Mapping to our `authenticity`: `verified` only if `isIssuerSignedAuthenticated && isDeviceSignedAuthenticated &&
isIssuerVerified && isMsoSigned && validationErrors.isNullOrEmpty()`. All five booleans go into `auth_checks`.
The backend recomputes the status from the booleans rather than trusting a status string from the device.

Trust model (say this out loud in Q&A): the backend can't re-verify a Tap2iD result, because the cryptography ran on
the phone. The prototype authenticates the device with a static `X-Device-Token` from `.env`. Production would use
device attestation (Play Integrity) or mTLS per enrolled reader.

## 6. Frontend flow

```
VisitList ──select──▶ Verify (visit header + two big buttons)
                         ├─ "Verify with mobile ID" ─▶ wallet prompt or QrPanel ─▶ Result
                         └─ "Manual fallback"       ─▶ ManualForm ───────────────▶ Result
Result ──"Save to audit log"──▶ AuditLog (highlight new row)
```

- DC API feature detection: `'DigitalCredential' in window`. If missing, hide flows A/B and say which browser is needed.
- Polling (C/D): every 2 s, stop at 90 s, show countdown and a cancel button.
- Design: plain, high-contrast, government-tool feel. Outcome colors always paired with an icon and text label.

## 7. Security and privacy decisions

| Concern | Decision |
|---|---|
| License key exposure | Backend-only; `.env`; never in frontend build. Acceptance test greps the bundle. |
| SSN handling | Masked input; sent once over HTTPS; compared in memory; never logged, never stored in audit, never echoed back except last 4 |
| Data minimization | Request only the claims the scoring engine uses (+ portrait at P1) |
| Audit integrity | Append-only (no update/delete routes) + SHA-256 hash chain; chain check endpoint |
| Score tampering | Results computed and held server-side; client saves by result id only |
| Seed data | Fully synthetic; SSNs in 9xx range; NPIs fake |
| HTTPS | Required for DC API and Credence registered origin; see plan.md § Hosting |

## 8. Hosting for the demo

The Cloud SDK requires a **registered HTTPS domain** that matches the `Origin` header. **Decided (Oct 9): Render free web service at `https://fieldverify-avyq.onrender.com`.** Options considered:

1. **Cloudflare quick tunnel** (`cloudflared tunnel --url http://localhost:8000`): free, fast, but the URL changes each
   run unless a named tunnel is set up, and the portal domain would have to be updated.
2. **Deploy to a free host** (e.g. Render for FastAPI serving the built frontend): stable URL, also gives Credence a
   "working prototype" link. Recommended for the final submission.
3. **localhost**: rejected by the portal (needs a valid hostname).

Consequences of Render:
- The Cloud SDK license is bound to the exact `https://<service>.onrender.com` origin, so the Render service must exist
  (even as a placeholder) before the key can be generated (T12a → T12b).
- Server-side calls set `Origin` themselves, so QR flows (C/D) can be developed against the real API from localhost.
  DC API flows (A/B) bind the wallet response to the **page origin**, so they only work when the page is served from
  the Render URL; test those by deploying (Render redeploys on git push).
- Free services sleep when idle (cold start ~30–60 s). Open the URL a minute before any demo or recording.
- Render builds from a GitHub repo, so the code repo must be pushed to GitHub (it's also the "code link" for Credence).

In demo mode, FastAPI serves `frontend/dist` so there is one origin. The Android app calls the same HTTPS URL.

## 9. Unknowns the build will answer

These are **not questions for the human**. Each is answered by a specific task, and the answer is written back here.

| # | Unknown | Answered by | Answer |
|---|---|---|---|
| 1 | Which Cloud SDK flow works with the candidate's wallet ID | T13 spike | _pending_ |
| 2 | Correct base URL: `/cloudsdk/playground` vs `/cloudsdkdev` | T12b | **`https://credenceid.com/cloudsdk/playground`** (Oct 9: `/v1/setup` → 200 with tokens, `expiresIn` 900 s; `/cloudsdkdev` → 401 INVALID_LICENSE_KEY). |
| 3 | Does the portal accept `localhost` as the registered domain, or is a tunnel needed from day one | T12 | **No.** Portal requires a real hostname ("Domain must be a valid hostname (e.g. https://yourapp.com)"). Decision: Render free deploy (see §8). |
| 4 | Are requested claims (portrait, address) set per request or on the reader profile | T13 | **On the profile** (Oct 9: initiate calls take no claims; the returned DCQL query reflects the profile). Need a custom profile with given/family name + birth date. |
| 5 | What `resDetails` contains for flows A/B | T13 fixture | _pending_ |
| 6 | Does the wallet ID present to the Tap2iD sample app on Android | A1 | _pending_ |
| 7 | Which `SdkConfig` signature the 2.0.0 artifact really has, and what's in `MdocAttributes` | A2 | _pending_ |
| 8 | PDF417 library | T19 | **zxing-wasm 3.1.4** (WebAssembly build of zxing-cpp, much stronger on PDF417 than the pure-JS port). Photo via `<input capture>`, decoded on-device, `textMode: Plain` (default HRI mode turns control chars into `<LF>` tokens). Real-card reliability still to confirm. |

Decided, no longer open: this is a separate git repo (not part of the `D:\projects` repo); Cloud SDK web first;
the candidate has a real wallet ID; one backend for both front ends.
