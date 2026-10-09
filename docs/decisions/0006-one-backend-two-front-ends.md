# ADR-0006: One backend, two front ends (web + Android)

- Status: Accepted (Oct 9 2026). Refines ADR-0001 (web first, not web only).

## Context
Credence's posting says "Android is a big part of our world", and their flagship in-person product is the Tap2iD SDK
on Android. ADR-0001 chose the Cloud SDK web app because it is the safest way to a working demo in five days.
We still want the Android story if it can be done safely.

## Decision
- All business logic lives in the **FastAPI backend**: enrollment records, scoring engine, outcome rules, audit log,
  hash chain. Front ends hold no scoring or audit logic.
- **Front end 1 (P0): React web app** on the Credence **Cloud SDK** (wallet via DC API / OpenID4VP).
- **Front end 2 (time-boxed stretch): Android reader app** in **Java** (one thin Kotlin wrapper for the SDK's
  suspend functions) on the Credence **Tap2iD SDK** (wallet via NFC/QR tap).
  It verifies on the device, then posts the claims and check results to `POST /api/verify/digital/tap2id`.
  The backend scores and logs it exactly like a web result.
- Android is attempted only if (a) the one-hour Tap2iD wallet-read test (task A1) passes, and (b) the web app is
  feature-frozen. Hard stop Tuesday Oct 13, 8:00 PM CT. If it isn't working end to end by then, it becomes the
  "phase 2" slide and is not submitted.
- One submission: one product with two front ends, or the web app alone.

## Alternatives considered
- **Java backend (Spring Boot)** so Android and backend share model classes: the shared contract is ~6 fields
  each way; FastAPI + pytest is faster to build and test the scoring rules in five days. Rejected.
- **Port the web app to Android**: a rewrite of logic in two places; scores could diverge. Rejected.
- **Android only**: highest risk (new platform, two devices, uncertain whether consumer wallet IDs present to a
  third-party reader). Rejected.
- **Web only**: safe, but misses the chance to show both SDKs. Kept as the fallback.

## Consequences
- The backend API is the product's core and must be front-end-neutral (no web-only assumptions in result shapes).
- Trust model difference: with Tap2iD, cryptographic checks run **on the reader device** and the backend trusts the
  device's report. The prototype uses a per-device API token (`X-Device-Token`); production would need device
  attestation or mTLS. This is stated openly in the README and is a good Q&A answer.
- Audit entries record `channel` (`web` / `android`) and `flow` (`A`–`D` / `tap2id`).
