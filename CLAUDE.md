# CLAUDE.md — FieldVerify

Instructions for any coding agent working in this repository. Read this file fully before doing anything.

## What this project is

FieldVerify is a web app that lets a Medicaid program-integrity auditor verify the identity of an enrolled
provider during an in-person site visit. It has two modes:

1. **Digital mode**: the provider presents a mobile ID from their phone wallet (Google / Apple / Samsung Wallet).
   Verification runs through the **Credence ID Cloud SDK** and the result is cryptographic.
2. **Manual fallback mode**: the auditor types the details from a physical ID (optionally scans the license
   barcode), and a scoring engine matches them against the provider's enrollment record.

Every verification is written to an append-only, tamper-evident audit log.

**One backend, two front ends** (ADR-0006): the FastAPI backend owns all records, scoring, outcomes, and the audit log.
The React web app (Cloud SDK) is the main front end. A time-boxed Android reader app (Tap2iD SDK) may be added as a
second front end that calls the same API. Never put scoring or audit logic in a front end.

It is a working prototype built for a job interview take-home (Credence ID, Solution Engineer). Deadline:
**Thursday, October 15, 2026, 1:00 PM Pacific**. Scope is deliberately small. Working beats complete.

## Read these, in this order

| File | Why |
|---|---|
| `_private/context.md` | The assignment, the audience, and the hard rules. Gitignored, never commit. |
| `docs/spec.md` | What to build: features, scoring rules, acceptance criteria, out-of-scope list |
| `docs/architecture.md` | How it fits together: components, data model, API, Credence integration |
| `docs/plan.md` | Phases, day-by-day schedule, checkpoints, risks |
| `tasks/todo.md` | The ordered task list. Work from here. |
| `docs/decisions/` | ADRs. Why things are the way they are. Read before changing a decision. |
| `docs/android/CONTEXT.md` | **Android work only.** Verified Tap2iD SDK API (from the real artifact), toolchain, backend contract, open questions. Read it before any Android change. |

Load only what the current task needs. Don't read the whole repo for a small change.

## Hard rules

1. **Do not write slide text, the pitch script, or video narration.** The assignment requires the deck and pitch
   to be the candidate's own words. If asked for these, decline and offer to explain the system instead.
2. **Do not copy code from Credence ID's GitHub samples** (`Tap2iD-SDK-Android`, `React-CloudSDK-Integration`).
   Their license forbids reuse or modification without written consent. Use them only to *read* how the API
   behaves. Write our own code against the public API reference.
3. **Never put the Cloud SDK license key in frontend code or a `VITE_` variable.** All Credence API calls that need
   the key go through our backend. (Credence's own sample injects the key at build time. We deliberately don't.)
4. **No real personal data in the repo.** Seed data is fake. Fake SSNs start with `9` (the SSA never issues these).
   The only real ID ever used is the candidate's own wallet ID during a live demo, and it is never written to disk
   beyond what the audit log stores (see rule 5).
5. **The audit log never stores raw SSNs, raw DOBs, or portraits.** It stores per-field outcomes
   (`match` / `partial` / `no_match` / `not_provided`), scores, and mode. See `docs/architecture.md` § Audit log.
6. **Never present a manual result as "identity verified".** Manual mode produces a *record match* only. The UI and
   the API must keep "authenticity" and "record match" as separate fields. See ADR-0002.
7. **Secrets live in `.env`** (gitignored). Keep `.env.example` current with every variable, with placeholder values.
8. **Don't invent Credence API fields.** If a response shape isn't confirmed in `docs/architecture.md` § Credence
   integration or by a logged real response, log the raw response first and then write the parser. Update the doc
   with what you saw.

## Pause and ask the human when

- Something must be installed or run on their machine (Node, Python, a tunnel, a deploy)
- An account, key, or portal setting is needed (Credence portal, hosting provider)
- A real wallet needs to be presented (only the human can do this)
- A spec rule conflicts with what the real API returns
- A decision in `docs/decisions/` would need to change

## Stack and commands

- Backend: Python 3.11+, FastAPI, SQLModel (SQLite), httpx, pytest. Lives in `backend/`.
- Web front end: React 18 + TypeScript + Vite. Lives in `frontend/`.
- Android front end: **Java**, plus two thin Kotlin files for `suspend` APIs: `Tap2iDVerifier.kt` (Credence SDK) and
  `SecondReader.kt` (open-source second read, ADR-0008). AGP 8.13.2, Gradle 8.14.3, compileSdk 36, minSdk 29, Tap2iD SDK 2.0.0. Lives in
  `android/`. **Read `docs/android/CONTEXT.md` first**; never use SDK APIs that aren't listed there.

The human is on **Windows** (PowerShell). Give commands that work there.

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1                          # PowerShell
pip install -r requirements.txt
python -m app.seed                                  # create + seed SQLite
uvicorn app.main:app --reload --port 8000
pytest -q

# frontend
cd frontend
npm install
npm run dev                                         # http://localhost:5173, proxies /api to :8000

# android (needs android/local.properties, see android/README.md)
cd android
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest
.\gradlew.bat :app:installDebug                     # phone connected over USB
```

## Code conventions

- Android: Java only, except `Tap2iDVerifier.kt`. Don't add more Kotlin.

- Python: type hints everywhere, `ruff` formatting, small pure functions in `scoring/` (no I/O there).
- Scoring engine is test-first: write the failing test in `backend/tests/test_scoring.py` before the rule.
- TypeScript: strict mode, no `any`, API types in `frontend/src/api/types.ts` mirror backend Pydantic models.
- Comments explain *why*, not *what*.
- Commit after each task in `tasks/todo.md` with a message that names the task ID (e.g. `T05: scoring names`).
- AI-assisted work is disclosed in the README (the assignment requires this). Keep the "How this was built" section honest.

## Definition of done for any task

- Acceptance criteria in `tasks/todo.md` are met
- `pytest -q` passes; frontend builds with `npm run build`
- No secrets or real personal data in the diff
- `tasks/todo.md` checkbox ticked, and any doc that changed is updated in the same commit
