"""Manual ingestion CLI: python -m app.workers.ingestion <scenario.json> [--ticker TICKER ...]"""
import asyncio
import argparse

from app.db import AsyncSessionLocal
from app.services.providers.replay import ReplayProvider, ReplayExhausted
from app.services.ingestion import ingest_observation


async def run(scenario_path: str, tickers: list[str] | None = None) -> None:
    provider = ReplayProvider(scenario_path)
    tickers = tickers or list(provider._timelines.keys())

    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            step = 0
            while True:
                try:
                    obs = await provider.get_stock(ticker)
                except ReplayExhausted:
                    break
                step += 1
                outcome = await ingest_observation(db, obs)
                extra = ""
                if outcome.result.value == "ACCEPTED":
                    extra = f" event_fired={outcome.event_fired} data_quality={outcome.data_quality}"
                print(f"[{ticker} step {step}] {outcome.result.value}{extra}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually run ingestion against a replay scenario file")
    parser.add_argument("scenario", help="Path to a data/scenarios/*.json replay file")
    parser.add_argument("--ticker", action="append", help="Limit to specific ticker(s); default all in file")
    args = parser.parse_args()
    asyncio.run(run(args.scenario, args.ticker))


if __name__ == "__main__":
    main()
