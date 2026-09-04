# Last-Visit Engine — Phase 7 Spec (DRAFT, awaiting sign-off)

Status: DRAFT — decisions below need approval before implementation.
Depends on: RELEVANCE_ATTENTION_SPEC.md (sections 3, 4, 6, 7, 9 — all frozen), SCORING_MODEL.md.
Scope: two endpoints (GET watchlist state + POST viewed-marker), and the last_viewed_at
semantics that connect them. Does NOT reopen any Phase 6.8 decision.

---

## 1. Endpoint contracts

  GET  /watchlists/{id}?objective={GROWTH|VALUE|STABILITY}   (objective optional)
  POST /watchlists/{id}/viewed

GET is read-only and side-effect-free with respect to last_viewed_at (see section 5).
POST is the only mutator of last_viewed_at, and accepts no body (see section 5).

---

## 2. Response shape (GET)

  {
    "watchlist_id": ...,
    "objective": "GROWTH" | "VALUE" | "STABILITY",   // the objective actually used this request
    "last_viewed_at": ISO8601 | null,                 // null on first-ever visit, see section 3
    "since_last_visit": {
      "meaningful_change_count": int,                 // = N, per RELEVANCE_ATTENTION_SPEC.md section 9
      "events": [ <explanation-contract object per RELEVANCE_ATTENTION_SPEC.md section 7>, ... ]
    },
    "instruments": [
      {
        "symbol": ...,
        "attention_tier": "HIGH" | "MEDIUM" | "LOW" | null,   // null if no scoreable event at all
        "top_event": <explanation-contract object> | null,
        "added_at": ISO8601                            // see section 4
      },
      ...
    ]
  }

`events` in `since_last_visit` is the full, non-deduplicated list per section 9 rule 1 (one
entry per eligible event, not per instrument). `instruments[].top_event` is the section-5
"top event tag" — the single winning event per instrument, which may or may not be the same
event object referenced anywhere in `since_last_visit.events`.

---

## 3. First-visit behavior

  [DECISION 9] What counts as "since last visit" when last_viewed_at is null?

  Option A: Treat null as "beginning of time" — every currently-eligible event on the
  watchlist counts toward N and appears in since_last_visit.events.
  Option B: Treat null as "nothing has changed yet" — since_last_visit is empty
  (meaningful_change_count: 0, events: []) until the first POST /viewed fires.

  Recommendation: Option A. A brand-new watchlist with real, currently-eligible events
  (e.g. a stock already at its 52-week high on day one) should not silently hide that from
  a first-time user just because there's no prior baseline — that would contradict the
  whole point of the feature. "Nothing to compare against yet" is a reason to show
  everything currently true, not a reason to show nothing.

---

## 4. Newly-added-stock behavior

  [DECISION 10] A stock added to the watchlist AFTER last_viewed_at, with no change
  events yet (it's just sitting there) — does it appear in since_last_visit at all?

  Recommendation: No. since_last_visit is event-driven per section 9's "N counts events"
  rule — a stock with zero eligible events contributes zero to N and appears nowhere in
  events, regardless of how recently it was added. Addition itself is not an event type in
  EVENT_TYPES and Phase 6.8 never defined one; inventing "WATCHLIST_ADD" as an eleventh
  event type now would silently reopen Phase 6.8's event taxonomy. If highlighting recently
  added stocks turns out to be wanted, it's a separate, new decision — not an inferred
  extension of "since last visit."

  The instrument DOES appear in the top-level `instruments` array immediately (its
  `added_at` timestamp lets the frontend badge it as new without touching event/N logic).

---

## 5. Last-viewed semantics (FROZEN going in — not up for debate)

  1. GET never mutates last_viewed_at, under any circumstance, including a fully
     successful render. This is a hard invariant: a client that calls GET but never
     calls POST /viewed must see the exact same since_last_visit on every subsequent
     GET, indefinitely.
  2. last_viewed_at is set ONLY by POST /watchlists/{id}/viewed succeeding.
  3. The new last_viewed_at value is server UTC time at the moment the POST is
     processed — NEVER a client-supplied timestamp. POST accepts no body; a body, if
     sent, is ignored (not merely unvalidated — actively ignored, so a client can't
     smuggle a timestamp override through an unchecked field).
  4. This ordering is deliberate and required: frontend renders GET's response
     successfully first, THEN calls POST. If GET's data fails to render (network
     drop, frontend exception, user navigates away before paint), last_viewed_at
     must remain unchanged — the unread events are not silently consumed.

---

## 6. Objective selection (FROZEN going in)

  GET /watchlists/{id}                  -> uses watchlist.objective (persisted default)
  GET /watchlists/{id}?objective=VALUE  -> uses VALUE for this response only

  The query param never mutates watchlist.objective. Changing the persisted default
  objective (if that's even a desired feature) is a separate endpoint/decision, not an
  implicit side effect of passing ?objective= on a GET.

  [DECISION 11] Is an invalid objective value (?objective=FOO) a 400, or a silent
  fallback to the watchlist's default?

  Recommendation: 400. Silent fallback on a malformed request hides frontend bugs — if
  the frontend sends a typo'd objective, better to fail loud in development than quietly
  serve GROWTH-flavored data when VALUE was intended.

---

## 7. N calculation

Direct application of RELEVANCE_ATTENTION_SPEC.md section 9 — no new decisions here.
N = meaningful_change_count = count of eligible events (any tier, UNAVAILABLE excluded)
under the objective resolved per section 6 above.

---

## 8. Failure / transaction semantics

  [DECISION 12] If POST /viewed succeeds at the DB layer but the response fails to
  reach the client (network drop after commit) — is that acceptable, or does the
  frontend need a way to detect and recover from it?

  Recommendation: Acceptable, with a documented tradeoff. last_viewed_at correctly
  advancing even though the client never got confirmation is the SAFE failure direction
  (worst case: user misses seeing events they've technically "acknowledged" — annoying,
  not data-corrupting). The alternative failure direction — advancing the client's local
  state without the server confirming — is the dangerous one, and this design avoids it
  by construction (server is the sole source of truth for last_viewed_at, per section 5).
  No additional idempotency mechanism is needed for v1; flag if real usage shows this
  losing events in practice.

---

## 9. Tests / acceptance criteria (minimum set before Phase 8 begins)

  1. First GET on a brand-new watchlist (last_viewed_at null) with a pre-existing
     eligible event returns it in since_last_visit (Decision 9, Option A).
  2. Repeated GET calls (no POST /viewed between them) return byte-identical
     since_last_visit on every call.
  3. POST /viewed sets last_viewed_at to server time regardless of any client-supplied
     body content.
  4. GET after POST /viewed with no new events returns meaningful_change_count: 0.
  5. A newly-added stock with zero events does not appear in since_last_visit.events,
     but does appear in instruments[] with its added_at populated.
  6. GET with ?objective=VALUE returns a different meaningful_change_count than GET
     with ?objective=STABILITY, for a watchlist where at least one event's relevance
     genuinely differs by objective (e.g. a downward PRICE_MOVE, per section 2d).
  7. GET with an invalid ?objective= value returns 400 (Decision 11 pending approval).
  8. A co-fired PRICE_MOVE + 52W_HIGH event contributes 2 to meaningful_change_count
     but produces exactly one instruments[].top_event (section 9 rule 1 + section 5).
  9. A STALE event appears in since_last_visit.events with data_status.state == "STALE"
     and a plain-language disclosure message, never a percentage (section 6/7 contract).
  10. An UNAVAILABLE event never appears anywhere in since_last_visit or as an
      instrument's top_event (section 4 rule 2 / section 9 rule 3).

---

## Next step

Approve/adjust Decisions 9-12 above, then implement GET first (it's read-only and
independently testable), then POST /viewed, then wire the frontend-facing integration
tests in section 9.
