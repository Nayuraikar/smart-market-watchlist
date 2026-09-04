from datetime import datetime, timezone
from decimal import Decimal

from app.services.ingestion import (
    check_price_volume, check_timestamp, compute_sequence,
    compute_data_quality, detect_price_move, IngestResult,
)
from app.schemas.market import MarketObservation


def _obs(price, volume=1000, observed_at="2026-09-05T04:00:00+00:00"):
    return MarketObservation(
        ticker="RELIANCE.NS", price=Decimal(str(price)), volume=Decimal(str(volume)),
        observed_at=datetime.fromisoformat(observed_at), source="test",
    )


def test_small_move_no_event():
    assert detect_price_move(Decimal("100"), Decimal("100.5")) is False


def test_big_move_fires_event():
    assert detect_price_move(Decimal("100"), Decimal("108")) is True


def test_negative_price_rejected():
    assert check_price_volume(_obs(-10)) == IngestResult.REJECTED_INVALID_PRICE


def test_negative_volume_rejected():
    assert check_price_volume(_obs(100, volume=-5)) == IngestResult.REJECTED_INVALID_VOLUME


def test_valid_price_volume_passes():
    assert check_price_volume(_obs(500, volume=1000)) is None


def test_sequence_is_monotonic_with_time():
    earlier = _obs(100, observed_at="2026-09-05T04:00:00+00:00")
    later = _obs(101, observed_at="2026-09-05T04:05:00+00:00")
    assert compute_sequence(later) > compute_sequence(earlier)


def test_stale_observation_flagged():
    old_obs = _obs(100, observed_at="2026-09-05T04:00:00+00:00")
    now = datetime(2026, 9, 5, 4, 5, 0, tzinfo=timezone.utc)  # 5 min later
    assert compute_data_quality(old_obs, now, stale_threshold_seconds=120) == "STALE"


def test_fresh_observation_not_flagged():
    recent_obs = _obs(100, observed_at="2026-09-05T04:00:00+00:00")
    now = datetime(2026, 9, 5, 4, 0, 30, tzinfo=timezone.utc)  # 30s later
    assert compute_data_quality(recent_obs, now, stale_threshold_seconds=120) == "FRESH"


def test_replay_exhausted_raises_custom_exception():
    import asyncio
    import json
    import tempfile
    from app.services.providers.replay import ReplayProvider, ReplayExhausted

    data = {"TESTTICKER": [
        {"price": "100", "volume": "1000", "observed_at": "2026-01-01T00:00:00+00:00", "source": "test"}
    ]}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = f.name

    async def _run():
        provider = ReplayProvider(path)
        await provider.get_stock("TESTTICKER")  # consumes the only observation
        try:
            await provider.get_stock("TESTTICKER")  # should raise cleanly, not RuntimeError
            assert False, "expected ReplayExhausted"
        except ReplayExhausted:
            pass  # correct
        except RuntimeError:
            assert False, "StopIteration leaked as RuntimeError — PEP 479 regression"

    asyncio.run(_run())
