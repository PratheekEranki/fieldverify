# ADR-0008: Android: optional second read (open-source) for name and date of birth

- Status: Accepted (Oct 13 2026)

## Context
The Tap2iD (in-person) license runs on Credence's **Age Check Profile 2.0**. A real read on Oct 13 confirmed it
shares only `issuing_authority`, `portrait` and `age_over_21`. The Tap2iD SDK has no way to request other fields
(`verifyMdoc` takes only the engagement config), and default profiles can't be edited; a custom profile needs
Credence support. The wallet itself will share name and date of birth if a reader asks. The candidate chose to keep
Tap2iD for the verdict and add a way to fetch the name and DOB as well.

## Decision
1. **Tap2iD stays the authenticity source.** Its result (issuer/device signatures, digests, trust chain, MSO
   validity) decides "genuine", unchanged.
2. When a Tap2iD read shared no name or DOB, the Android result screen offers a **second read** with the open-source
   Multipaz reader library (`org.multipaz:multipaz:0.101.0`, OpenWallet Foundation): NFC tap or wallet QR, then
   Bluetooth. It requests `given_name`, `family_name`, `birth_date`, `issuing_authority` (`SecondReader.kt`).
3. `POST /api/verify/digital/second-read` (device token) accepts the details only if the second read's own checks all
   pass (issuer signature, device signature, digests, validity window), the document is an mDL, and its issuing
   authority equals the first read's. It scores them and records `match_source = "second_read"`.
4. Outcomes for `second_read` are **capped at yellow** ("…match record (not checked by Credence): confirm"); a failed
   Tap2iD verdict stays red. Labels say "second read" in the app, the web result page and the audit log.

## Consequences
- Two taps and two approvals on the holder phone.
- **Weak link between the reads.** Nothing cryptographically ties the second session to the first; matching issuer is
  a sanity check, not proof. Someone could swap phones between reads. That is why the cap is yellow and the auditor
  confirms the photo. The real fix is a Credence profile that includes name/DOB in the Tap2iD read itself (support
  request); when that exists, this path stops appearing (it only shows when `match_source == "none"`).
- The second read's issuer is not checked against any trust list (we only have Credence's, and it isn't exposed).
- Adds a second Kotlin file (`SecondReader.kt`); the library's APIs are `suspend`. ~12 MB larger APK.
- Not tested end to end until the candidate runs it on two phones.
