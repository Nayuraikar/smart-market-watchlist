"""Historical market ingestion worker.

Replays saved historical JSON observations periodically and
persists them through the existing ingestion service.

Run:
    python -m app.workers.fresh_ingestion
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.db import AsyncSessionLocal, engine
from app.models import Instrument
from app.services.ingestion import ingest_observation
from app.services.providers.simulated import SimulatedMarketProvider


logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = int(
    os.environ.get("SIMULATION_INTERVAL_SECONDS", "30")
)

DATABASE_RETRY_SECONDS = int(
    os.environ.get("DATABASE_RETRY_SECONDS", "5")
)


async def wait_for_database() -> None:
    """Wait until PostgreSQL is accepting connections."""

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))

            logger.info("Database connection established")
            return

        except Exception as exc:
            logger.warning(
                "Database unavailable: %s. Retrying in %s seconds",
                exc,
                DATABASE_RETRY_SECONDS,
            )
            await asyncio.sleep(DATABASE_RETRY_SECONDS)


async def get_instrument_tickers() -> list[str]:
    """Return all instruments currently present in the catalog."""

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Instrument.ticker).order_by(Instrument.ticker)
        )
        return list(result.scalars().all())


async def ingest_cycle(provider: SimulatedMarketProvider) -> None:
    """Run one complete market-data ingestion cycle."""

    tickers = await get_instrument_tickers()

    if not tickers:
        logger.warning("No instruments found in catalog")
        return

    logger.info(
        "Starting historical market ingestion for %s instruments",
        len(tickers),
    )

    cycle_started_at = datetime.now(timezone.utc)

    try:
        observations = await provider.get_stocks(tickers)

    except Exception as exc:
        logger.exception("Market provider failed during ingestion cycle: %s", exc)
        return

    if not observations:
        logger.warning("Provider returned no observations")
        return

    accepted = 0
    rejected = 0
    events = 0

    for observation in observations:
        try:
            # Use a separate session per observation.
            #
            # ingest_observation() commits internally, so isolating each
            # observation prevents one database/provider error from
            # poisoning the remainder of the cycle.
            async with AsyncSessionLocal() as db:
                outcome = await ingest_observation(db, observation)

            if outcome.result.value == "ACCEPTED":
                accepted += 1

                if outcome.event_fired:
                    events += 1

                logger.info(
                    "Ingested %s: %s event_fired=%s data_quality=%s",
                    observation.ticker,
                    outcome.result.value,
                    outcome.event_fired,
                    outcome.data_quality,
                )
            else:
                rejected += 1

                logger.warning(
                    "Rejected %s: %s",
                    observation.ticker,
                    outcome.result.value,
                )

        except Exception as exc:
            rejected += 1

            logger.exception(
                "Failed to persist observation for %s: %s",
                observation.ticker,
                exc,
            )

    elapsed = (
        datetime.now(timezone.utc) - cycle_started_at
    ).total_seconds()

    logger.info(
        "Historical simulation cycle complete: "
        "requested=%s received=%s accepted=%s rejected=%s "
        "events=%s elapsed=%.2fs",
        len(tickers),
        len(observations),
        accepted,
        rejected,
        events,
        elapsed,
    )


async def run(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> None:
    """Run the fresh ingestion worker continuously."""

    if interval_seconds <= 0:
        raise ValueError("Simulation interval must be positive")

    provider = SimulatedMarketProvider(os.environ.get(
        "REPLAY_SCENARIO", "data/scenarios/historical_update_57.json"
    ))

    logger.info(
        "Starting historical market ingestion worker "
        "(interval=%ss)",
        interval_seconds,
    )

    await wait_for_database()

    try:
        while True:
            cycle_started_at = datetime.now(timezone.utc)

            try:
                await ingest_cycle(provider)

            except Exception as exc:
                logger.exception(
                    "Unexpected ingestion-cycle failure: %s",
                    exc,
                )

            elapsed = (
                datetime.now(timezone.utc) - cycle_started_at
            ).total_seconds()

            sleep_seconds = max(
                0,
                interval_seconds - int(elapsed),
            )

            logger.info(
                "Next ingestion cycle in %s seconds",
                sleep_seconds,
            )

            await asyncio.sleep(sleep_seconds)

    except asyncio.CancelledError:
        logger.info("Historical simulation worker shutting down")
        raise

    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    interval_seconds = int(
        os.environ.get(
            "SIMULATION_INTERVAL_SECONDS",
            str(DEFAULT_INTERVAL_SECONDS),
        )
    )

    asyncio.run(run(interval_seconds))


if __name__ == "__main__":
    main()