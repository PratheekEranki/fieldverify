# ADR-0007: Work with Credence's Age Check profile; complete the match from the physical ID

- Status: Accepted (Oct 12 2026)

## Context
The Cloud SDK license is bound to a Credence profile, and the profile decides which fields a wallet shares. The only
profiles available self-service are read-only age-check profiles. For an mDL, "Age Check Profile 2.0" shares the
issuing authority, the portrait and an age attestation, and **no name or date of birth**. Custom profiles are
created by Credence support (requested Oct 12, no answer yet). The demo can't depend on that answer.

## Decision
Support the Age Check profile end to end:
1. A verified credential that shares no name/DOB gets the yellow outcome
   "Credential genuine: no name or DOB shared, compare the photo" (never red: nothing compared is not a mismatch).
2. The result page offers **Complete the record match**: the auditor confirms the credential photo matches the
   person, then takes name and DOB from the physical ID (barcode scan or typing). `POST /api/verify/digital/supplement`
   scores them against the enrollment record.
3. The completed result keeps authenticity from Credence and records `match_source = "id_details"`, with its own
   labels ("Credential genuine + photo confirmed; ID details match record", etc.). It never uses the
   "Verified: cryptographic + record match" label, which is reserved for `match_source = "wallet"`.
4. `match_source` (wallet / id_details / manual / none) is stored on every audit entry and covered by the hash chain.
5. Age attestations the wallet shares (e.g. `age_over_21`) are shown as "Shared by the wallet" and never scored.

## Alternatives considered
- **Wait for a custom profile:** blocks the demo on a third party.
- **Treat the photo comparison alone as verification:** too weak for enrollment fraud; no link to the record.
- **Label the completed result "Verified":** would overstate it. The name/DOB aren't cryptographically bound to the
  credential, so an auditor or reviewer must be able to tell the difference at a glance.

## Consequences
- The live demo works today with the profile we have; when a custom profile arrives, the same screens show the
  wallet-attested green result with no code change.
- Good pitch material: it shows how Credence's privacy-minimal default plays out in a real workflow.
