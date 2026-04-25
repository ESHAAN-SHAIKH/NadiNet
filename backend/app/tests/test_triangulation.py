"""
Tests for the triangulation state machine.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import uuid
from app.services.triangulation import compute_c_score, process_signal, CORROBORATION_WINDOW_HOURS
from app.models.signal import Signal
from app.models.reporter import Reporter


def make_signal(
    reporter_id=None,
    source_channel="whatsapp",
    zone_id="Zone 4",
    need_category="nutrition",
    urgency=3,
    hours_ago=1,
    state="watch",
    corroboration_id=None,
):
    s = Signal(
        id=uuid.uuid4(),
        reporter_id=reporter_id,
        source_channel=source_channel,
        zone_id=zone_id,
        need_category=need_category,
        urgency=urgency,
        collected_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        state=state,
        corroboration_id=corroboration_id,
    )
    return s


def make_reporter(trust_score=0.65):
    return Reporter(
        id=uuid.uuid4(),
        phone=f"+91{uuid.uuid4().int % 10000000000:010d}",
        trust_score=trust_score,
    )


class TestCScoreComputation:
    def test_same_channel_reduces_score(self):
        r1 = make_reporter()
        r2 = make_reporter()
        s1 = make_signal(reporter_id=r1.id, source_channel="whatsapp")
        s2 = make_signal(reporter_id=r2.id, source_channel="whatsapp")  # same channel
        c = compute_c_score(s1, s2, r1, r2)
        # No source diversity bonus; score is lower
        assert c < 1.0

    def test_different_channel_increases_score(self):
        r1 = make_reporter()
        r2 = make_reporter()
        s1 = make_signal(reporter_id=r1.id, source_channel="whatsapp")
        s2 = make_signal(reporter_id=r2.id, source_channel="ocr")
        c_different = compute_c_score(s1, s2, r1, r2)
        s2_same = make_signal(reporter_id=r2.id, source_channel="whatsapp")
        c_same = compute_c_score(s1, s2_same, r1, r2)
        assert c_different > c_same

    def test_c_clamped_to_zero_one(self):
        r1 = make_reporter()
        r2 = make_reporter()
        s1 = make_signal(reporter_id=r1.id)
        s2 = make_signal(reporter_id=r2.id)
        c = compute_c_score(s1, s2, r1, r2)
        assert 0.0 <= c <= 1.0

    def test_same_reporter_reduces_independence(self):
        r = make_reporter()
        s1 = make_signal(reporter_id=r.id)
        s2 = make_signal(reporter_id=r.id)  # same reporter
        c_same = compute_c_score(s1, s2, r, r)

        r2 = make_reporter()
        s3 = make_signal(reporter_id=r2.id)
        c_diff = compute_c_score(s1, s3, r, r2)
        assert c_same < c_diff


class TestProcessSignal:
    @pytest.mark.asyncio
    async def test_single_signal_stays_watch(self):
        """A single signal with no matching watch signals stays in watch state."""
        db = AsyncMock()
        # No matching signals in DB
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        r_id = uuid.uuid4()
        signal = make_signal(reporter_id=r_id)
        db.add(signal)

        need = await process_signal(db, signal)
        assert need is None
        assert signal.state == "watch"

    @pytest.mark.asyncio
    async def test_same_reporter_not_corroborated(self):
        """Two signals from the same reporter should NOT corroborate."""
        reporter_id = uuid.uuid4()
        existing = make_signal(reporter_id=reporter_id)

        db = AsyncMock()
        # Returns empty because query filters reporter_id != new_signal.reporter_id
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # same reporter filtered out
        db.execute = AsyncMock(return_value=mock_result)

        new_sig = make_signal(reporter_id=reporter_id)
        need = await process_signal(db, new_sig)
        assert need is None

    @pytest.mark.asyncio
    async def test_different_reporters_same_channel_corroborated(self):
        """Two signals from different reporters, same channel → corroborated (C < 1.0)."""
        r1_id = uuid.uuid4()
        r2_id = uuid.uuid4()

        existing = make_signal(reporter_id=r1_id, source_channel="whatsapp", hours_ago=5)
        new_sig = make_signal(reporter_id=r2_id, source_channel="whatsapp", hours_ago=0)

        reporter1 = make_reporter(0.80)
        reporter1.id = r1_id
        reporter2 = make_reporter(0.75)
        reporter2.id = r2_id

        db = AsyncMock()
        # First execute: matching signals
        result1 = MagicMock()
        result1.scalars.return_value.all.return_value = [existing]
        # Second execute: urgencies
        result2 = MagicMock()
        result2.fetchall.return_value = [(3,), (4,)]

        db.execute = AsyncMock(side_effect=[result1, result2])
        db.get = AsyncMock(side_effect=[reporter1, reporter2, None])
        db.flush = AsyncMock()
        db.add = MagicMock()

        need = await process_signal(db, new_sig)
        assert need is not None
        assert new_sig.state == "active"
        assert need.c_score < 1.0  # same channel reduces C

    @pytest.mark.asyncio
    async def test_different_reporters_different_channel_higher_c(self):
        """Different reporters + different channels → higher C score than same channel."""
        r1_id = uuid.uuid4()
        r2_id = uuid.uuid4()

        # Same channel scenario C
        s1a = make_signal(reporter_id=r1_id, source_channel="whatsapp")
        s1b = make_signal(reporter_id=r2_id, source_channel="whatsapp")
        r1 = make_reporter(); r1.id = r1_id
        r2 = make_reporter(); r2.id = r2_id
        c_same = compute_c_score(s1a, s1b, r1, r2)

        # Different channel scenario C
        s2a = make_signal(reporter_id=r1_id, source_channel="whatsapp")
        s2b = make_signal(reporter_id=r2_id, source_channel="ocr")
        c_diff = compute_c_score(s2a, s2b, r1, r2)

        assert c_diff > c_same

    @pytest.mark.asyncio
    async def test_signal_older_than_72h_no_match(self):
        """Signal older than 72 hours should not be matched."""
        r1_id = uuid.uuid4()
        old_signal = make_signal(reporter_id=r1_id, hours_ago=73)

        db = AsyncMock()
        # Query should return no results (filtered by collected_at >= window_start)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []  # no match because of time filter
        db.execute = AsyncMock(return_value=result)

        new_sig = make_signal(reporter_id=uuid.uuid4(), hours_ago=0)
        need = await process_signal(db, new_sig)
        assert need is None
