# ADR-0001: Build a web app on the Credence Cloud SDK, not an Android app on Tap2iD

- Status: Accepted (Oct 9 2026)

## Context
Credence offers two SDKs that fit an in-person identity check:
- **Tap2iD SDK** (Android/iOS/Windows): native; the verifier device reads the mDL over NFC/QR/BLE. Kotlin, Android 10+,
  90-day evaluation key.
- **Cloud SDK** (browser + REST): the wallet presents through the Digital Credentials API or OpenID4VP (QR / deep link).
  Supports Google, Apple, Samsung Wallet and the CA DMV app.

The candidate has five days, strong Python/full-stack skills, no Kotlin/Android experience, and a real ID in a phone wallet.

## Decision
Build a React + FastAPI web app on the **Cloud SDK**.

## Alternatives considered
- **Tap2iD Android app**: closer to Credence's flagship in-person product and the "tap" story, but learning Android
  plus the SDK in five days puts the working demo at risk, and it needs two phones.
- **Both**: not achievable well in five days.

## Consequences
- Runs on any auditor laptop/tablet with a supported browser; no app install. Good pitch point.
- Needs a registered HTTPS domain, so hosting is part of the work (task T18).
- Browser support limits for DC API flows (Chrome 141+, Safari 17.4+).
- Tap2iD on a rugged Android device becomes a credible "phase 2" in the pitch.
