# ADR-0002: Keep "authenticity" and "record match" as separate signals

- Status: Accepted (Oct 9 2026)

## Context
An early design gave both modes a single "confidence %", with digital at 95–100% and manual at 0–100%. But
cryptographic verification is pass/fail, and a manual match only shows that someone *knows* the provider's details.
Merging them on one scale overstates manual results and muddles what the SDK actually proves. The audience
(Credence's identity engineers) will notice.

## Decision
- **Authenticity**: `verified` / `failed` / `not_checked`, from Credence checks only.
- **Record match**: 0–100 score + band, from our scoring engine, used in both modes.
- Outcome label is derived from both (spec §3). Manual mode can never be labelled "Verified".

## Alternatives considered
- Single blended score: simpler UI, but misleading and hard to defend.
- Digital-only, no fallback: cleaner, but ignores the real field case (no wallet ID, dead phone).

## Consequences
- The UI shows two panels, which is slightly more complex but clearer.
- Gives a precise answer to "what if an impostor knows the details?": that's why authenticity exists, and why manual
  results are labelled weaker and require a photo check.
