# Submission checklist

- Source: this repository, including committed historical JSON.
- Setup: follow README.md; `./start.sh` runs the full demo.
- Product pitch: PRODUCT_PITCH.md (100 words).
- Watchlist creation/management: implemented with ownership checks.
- Latest information: latest replayed historical observation, explicitly labeled, not a live exchange quote.
- Return later: persisted acknowledgement boundary and stable browser-session comparison window.
- Meaningful change: absolute price moves at or above 2%, scored by objective.
- Stale/delayed/conflicting data: timestamps, quality labels, sequence rejection and atomic writes; missing source metrics stay explicit.
- Scale: one ingestion stream shared by all users, indexed history, bounded chart reads, no per-user market API calls. Event-feed pagination and cursor persistence remain future improvements; do not claim unlimited scale.
- Reliability: committed data permits offline runtime even when collection is rate-limited.
- Tests: backend suite, frontend lint/build and GitHub CI included.

The challenge permits architectural tradeoffs. Historical replay demonstrates latest state relative to the simulation clock. It does not satisfy a separate requirement for real-time exchange quotes, which the pasted challenge does not explicitly mandate. Explain this choice in the presentation.
