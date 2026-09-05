"""
Replay historical observations through the normal ingestion pipeline.

Normal historical replay:

    python -m app.workers.historical_replay \
        data/scenarios/historical_baseline_57.json

    python -m app.workers.historical_replay \
        data/scenarios/historical_update_57.json

Demo update replay:

    python -m app.workers.historical_replay \
        data/scenarios/historical_update_57.json \
        --rebase-to-now

In --rebase-to-now mode:
    - historical prices remain unchanged
    - observation order remains unchanged
    - timestamps are rebased to the current time
    - timestamps remain strictly increasing
    - timestamps are guaranteed to occur after the latest watchlist visit
    - the normal ingestion/change-detection pipeline is still used
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import AsyncSessionLocal
from app.models.core import Watchlist
from app.services.ingestion import ingest_observation
from app.services.providers.replay import ReplayExhausted, ReplayProvider


async def get_replay_start_time(
    db,
    observation_count: int,
) -> datetime:
    """
    Choose a safe timestamp window for replay.

    We want every rebased observation to:
        1. be after the latest watchlist last_viewed_at
        2. not be in the future
        3. remain strictly chronological

    Example for 5 observations:

        10:30:06
        10:30:07
        10:30:08
        10:30:09
        10:30:10

    The worker waits if necessary so that the first timestamp is
    guaranteed to be after the latest watchlist visit.
    """

    result = await db.execute(
        select(func.max(Watchlist.last_viewed_at))
    )

    latest_last_viewed = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    # Leave one extra second of safety after the latest visit.
    if latest_last_viewed is not None:
        required_start = latest_last_viewed + timedelta(
            seconds=observation_count + 1
        )

        if required_start > now:
            wait_seconds = (
                required_start - now
            ).total_seconds()

            print(
                f"Waiting {wait_seconds:.1f}s so replay timestamps "
                f"occur after the latest watchlist visit..."
            )

            await asyncio.sleep(wait_seconds)

            now = datetime.now(timezone.utc)

    # End the replay window at approximately "now".
    # For 5 observations:
    #
    #   now - 4 sec
    #   now - 3 sec
    #   now - 2 sec
    #   now - 1 sec
    #   now
    #
    # This keeps all timestamps in the past/current,
    # never in the future.
    return now - timedelta(
        seconds=max(0, observation_count - 1)
    )


async def run(
    scenario_path: str,
    tickers: list[str] | None = None,
    rebase_to_now: bool = False,
) -> None:
    provider = ReplayProvider(scenario_path)

    if tickers is None:
        tickers = list(provider._timelines.keys())

    total_observations = 0
    total_accepted = 0
    total_rejected = 0
    total_events = 0

    print()
    print("=" * 64)
    print("HISTORICAL REPLAY")
    print("=" * 64)
    print(f"Scenario: {scenario_path}")
    print(f"Tickers : {len(tickers)}")

    if rebase_to_now:
        print("Mode    : REBASE TO NOW")
        print(
            "Prices  : SAVED SCENARIO VALUES (see scenario source/provenance)"
        )
        print(
            "Dates   : REPLAY TIMESTAMPS"
        )
    else:
        print("Mode    : ORIGINAL HISTORICAL TIMESTAMPS")

    print()

    async with AsyncSessionLocal() as db:

        # ---------------------------------------------------------
        # Determine replay timestamp window.
        # ---------------------------------------------------------

        replay_start = None
        replay_step_seconds = 1

        if rebase_to_now:
            max_observations = 0

            for ticker in tickers:
                timeline = provider._timelines.get(ticker, [])
                max_observations = max(
                    max_observations,
                    len(timeline),
                )

            if max_observations == 0:
                print("No observations found.")
                return

            replay_start = await get_replay_start_time(
                db,
                max_observations,
            )

            print(
                "Replay timestamp window:"
            )
            print(
                f"  start = {replay_start.isoformat()}"
            )
            print(
                f"  end   = "
                f"{(
                    replay_start
                    + timedelta(
                        seconds=max_observations - 1
                    )
                ).isoformat()}"
            )
            print()

        # ---------------------------------------------------------
        # Replay each ticker.
        # ---------------------------------------------------------

        for ticker in tickers:

            step = 0
            accepted = 0
            events = 0

            while True:

                try:
                    observation = await provider.get_stock(
                        ticker
                    )

                except ReplayExhausted:
                    break

                # -------------------------------------------------
                # Rebase timestamps when requested.
                # -------------------------------------------------

                if rebase_to_now:
                    rebased_timestamp = (
                        replay_start
                        + timedelta(
                            seconds=step
                        )
                    )

                    observation = observation.model_copy(
                        update={
                            "observed_at": rebased_timestamp
                        }
                    )

                step += 1
                total_observations += 1

                # -------------------------------------------------
                # Normal ingestion pipeline.
                # -------------------------------------------------

                if rebase_to_now:
                    outcome = await ingest_observation(
                        db,
                        observation,
                        now=observation.observed_at,
                    )
                else:
                    outcome = await ingest_observation(
                        db,
                        observation,
                    )

                if outcome.result.value == "ACCEPTED":

                    accepted += 1
                    total_accepted += 1

                    if outcome.event_fired:
                        events += 1
                        total_events += 1

                else:
                    total_rejected += 1

            print(
                f"{ticker:<20} "
                f"observations={step:<4} "
                f"accepted={accepted:<4} "
                f"events={events}"
            )

    print()
    print("=" * 64)
    print("REPLAY COMPLETE")
    print("=" * 64)
    print(f"Tickers processed : {len(tickers)}")
    print(f"Observations      : {total_observations}")
    print(f"Accepted          : {total_accepted}")
    print(f"Rejected          : {total_rejected}")
    print(f"Events fired      : {total_events}")
    print()


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Replay historical observations through "
            "normal ingestion."
        )
    )

    parser.add_argument(
        "scenario",
        help="Historical replay JSON file",
    )

    parser.add_argument(
        "--ticker",
        action="append",
        help=(
            "Replay only a specific ticker. "
            "May be supplied multiple times."
        ),
    )

    parser.add_argument(
        "--rebase-to-now",
        action="store_true",
        help=(
            "Keep historical prices but replay their "
            "timestamps immediately after the latest "
            "watchlist visit."
        ),
    )

    args = parser.parse_args()

    asyncio.run(
        run(
            args.scenario,
            args.ticker,
            args.rebase_to_now,
        )
    )


if __name__ == "__main__":
    main()