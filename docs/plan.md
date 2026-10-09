# Plan — FieldVerify

Status: draft v2 (Oct 9 2026). Tasks themselves live in `tasks/todo.md`.
v2: today = backend + web app; one backend with two front ends (ADR-0006); Android time-boxed to Tuesday.

## Deadline math

- Submit by **Thu Oct 15, 1:00 PM PT = 3:00 PM CT**. Internal target: **submitted by 11:00 AM CT Thursday.**
- The deck and the video are the candidate's own work and need **all of Wednesday** (draft the deck in short sessions
  from Sunday on).
- **Web app feature freeze: Monday night.** Android gets **Tuesday only, hard stop 8:00 PM CT**.

## Strategy

1. **Backend first, today.** Everything both front ends need (records, scoring, outcomes, audit log) is plain Python
   with no external dependencies, so it can be built and tested right away.
2. **Web front end on top of it today**, manual path first, so there's a working demo tonight.
3. **External risks early, but not blocking.** The Credence portal signup (15 minutes, the human) happens today while
   the backend is being built. The wallet-flow spike and the Tap2iD read test happen Saturday morning.
4. **Vertical slices.** Each phase ends with something demoable end to end.
5. **Android only if it's safe**: A1 test passed on Saturday, web app frozen Monday, Tuesday only.

## Schedule

| Day | Phase | Goal | Checkpoint |
|---|---|---|---|
| **Fri Oct 9** | 1. Backend + web manual path | Tools installed, scaffold, models, scoring engine, manual API, audit log + hash chain, web UI for visits / manual verify / result / audit log. Human: Credence portal signup. | **A** (tonight, or Sat morning at the latest): manual verify → result → saved in audit log, on localhost |
| **Sat Oct 10** | 2. Digital web path | Wallet-flow spike, Credence client, digital API, wallet flow in the browser, error paths. Human: A1 Tap2iD test (1 h). | **B**: real wallet ID → "Verified" result in the web app, 3× in a row |
| **Sun Oct 11** | 3. Hosting + P1 features | HTTPS hosting + registered domain, license barcode scan, portrait, customer integration guide | **C**: full demo on the HTTPS URL |
| **Mon Oct 12** | 3. Polish + freeze | UI polish, README, demo hardening, troubleshooting log tidy-up. Android backend endpoint if A1 passed. | **D: web feature freeze** |
| **Tue Oct 13** | 4. Android (if A1 passed) | Android scaffold, Tap2iD init, tap → backend → result → audit | **Go/no-go 8:00 PM CT**: works 3× end to end, or it becomes a "phase 2" slide |
| **Wed Oct 14** | 5. Deliverables | Human: deck + video. Agent: bug fixes only, final verification. | Video uploaded and opens without login |
| **Thu Oct 15** | Submit | Final check, send the email by 11:00 AM CT | Sent |

Sunday and Monday have buffer on purpose. If Saturday's digital path runs long, it eats Sunday, not Wednesday.

## Fallbacks

| If… | Then… |
|---|---|
| Checkpoint A slips past Saturday noon | Drop the hash chain to P2; keep audit list + CSV |
| The wallet ID works in no Cloud SDK flow by Saturday night | Email support@credenceid.com with the exact error; record a Digital ID Playground run as backup footage; the pitch leads with manual mode + the integration design |
| Render deploys are slow to iterate | Develop QR flows locally; deploy only to test DC API flows |
| A1 fails (wallet ID doesn't read on Tap2iD sample) | No Android. Tuesday becomes polish + deck time. "Phase 2" slide only |
| Android isn't working end to end at 8:00 PM Tuesday | Stop. Don't submit any Android code as working. "Phase 2" slide |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Candidate's wallet ID doesn't work with any Cloud SDK flow | Medium | High | Spike Saturday morning; ask Credence support early; backup footage; manual mode still demoable |
| Registered HTTPS domain blocks local dev | Happened | Medium | Portal rejects localhost → Render URL locked early (T12a); QR flows testable from localhost; DC API flows tested on Render |
| DC API browser support gaps (cross-device desktop → phone) | Medium | Medium | Demo from the setup the spike proved; QR flows C/D as alternative |
| Response shapes differ from docs | High | Low | Log the raw response first, write the parser against the fixture (CLAUDE.md rule 8) |
| Android eats deck time | High | High | Hard stop Tuesday 8 PM; deck drafted from Sunday |
| Scope creep | High | High | P2 only after Checkpoint D; freeze Monday |
| Live demo fails during recording | Medium | High | Record multiple takes; rehearse with the demo checklist |
| Using Credence sample code by accident | Low | High (license) | CLAUDE.md rule 2 |
| Real personal data in the repo | Medium | High | Demo provider from `.env` only (ADR-0004) |

## Who does what

| Candidate | Agent |
|---|---|
| Install tools; portal signup; key generation; domain registration | Scaffolding, all app code, tests |
| Present the real wallet ID during spikes and tests; run A1 | Debug from logs and recorded fixtures |
| Approve tunnel/deploy; Android device setup | Write deploy config and the exact steps |
| Pitch angle, deck, script | README, customer docs, diagrams to redraw, screenshots, demo checklist |
| Record the video; send the email | Final acceptance check |
