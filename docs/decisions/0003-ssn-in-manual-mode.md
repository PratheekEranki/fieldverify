# ADR-0003: Use SSN as a match field in manual mode, with strict handling

- Status: Accepted (Oct 9 2026)

## Context
Healthcare commonly uses SSN for record matching (e.g. ER registration alongside insurance). It is the most unique
field available for matching against a provider enrollment record, which stores SSN/TIN for individual providers.
It is also a knowledge factor: knowing it doesn't prove identity, and it is high-risk data to handle.
Federal SSN verification services (SSNVS, eCBSV) are not available for this use case.

## Decision
- SSN is an optional manual-mode field with the highest weight (30).
- Compared server-side against the (synthetic) enrollment record only. No federal lookup.
- Masked input; never logged, never stored in the audit log (only `match`/`partial`/`no_match`/`not_provided`), never
  returned except as last 4.
- Not part of digital mode (wallet IDs don't carry it).

## Alternatives considered
- Leave SSN out: safer, but weaker matching and doesn't reflect real healthcare practice.
- Last 4 only: less sensitive, but much weaker as a match signal.

## Consequences
- Stronger manual matching and a realistic story.
- Must be defended on data handling in Q&A. The answer is the list above.
