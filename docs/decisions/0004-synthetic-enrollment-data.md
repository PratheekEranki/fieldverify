# ADR-0004: Synthetic enrollment data, with the demo identity injected from .env

- Status: Accepted (Oct 9 2026)

## Context
A real state enrollment system (MMIS/PECOS) isn't reachable. The digital demo still has to match the candidate's real
wallet ID against an "enrolled provider", and real personal data must not land in a public repo.

## Decision
- SQLite seeded with 15 synthetic providers (fake NPIs that pass the Luhn check, SSNs in the never-issued 9xx range).
- One extra "demo provider" is created at seed time from `DEMO_PROVIDER_*` variables in `.env` (gitignored).

## Alternatives considered
- Query the public NPPES NPI API: real data about real people for a demo; rate limits; no DOB/SSN anyway.
- Hard-code the candidate's details in seed: leaks personal data into the repo.

## Consequences
- The pitch says plainly: "In production this connects to the state's enrollment system; for the demo it's synthetic."
- The scoring engine is isolated from the data source, so swapping in a real connector is a contained change.
