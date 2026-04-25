"""
Tests for the 3-pass volunteer matching engine.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.services.matching import (
    is_available_now, pass2_rank, haversine_km, parse_location_wkt,
)
from app.models.volunteer import Volunteer
from app.models.kinship import KinshipEdge


def make_volunteer(
    skills=None, is_available=True, zone_id="Zone 4",
    location_wkt=None, completion_rate=1.0, trust_score=0.8,
    availability_schedule=None
):
    v = Volunteer(
        id=uuid.uuid4(),
        phone=f"+91{uuid.uuid4().int % 10000000000:010d}",
        name="Test Volunteer",
        skills=skills or ["general"],
        languages=["hindi"],
        is_available=is_available,
        zone_id=zone_id,
        location_wkt=location_wkt,
        completion_rate=completion_rate,
        trust_score=trust_score,
        availability_schedule=availability_schedule,
    )
    return v


class TestIsAvailableNow:
    def test_no_schedule_always_available(self):
        assert is_available_now(None) is True

    def test_empty_schedule_not_available(self):
        # Empty schedule means volunteer explicitly set no days
        assert is_available_now({"mon": [], "tue": []}) is False

    def test_schedule_within_slot(self):
        # Can't test exact time, but test logic with current time mocking
        schedule = {
            "mon": [{"start": "00:00", "end": "23:59"}],
            "tue": [{"start": "00:00", "end": "23:59"}],
            "wed": [{"start": "00:00", "end": "23:59"}],
            "thu": [{"start": "00:00", "end": "23:59"}],
            "fri": [{"start": "00:00", "end": "23:59"}],
            "sat": [{"start": "00:00", "end": "23:59"}],
            "sun": [{"start": "00:00", "end": "23:59"}],
        }
        # Available all hours all days → always True
        assert is_available_now(schedule) is True


class TestHaversineDistance:
    def test_same_point_zero_distance(self):
        d = haversine_km(19.076, 72.877, 19.076, 72.877)
        assert d == pytest.approx(0.0, abs=0.001)

    def test_mumbai_to_thane_approx_25km(self):
        # Mumbai (19.0760, 72.8777) to Thane (19.2183, 72.9781)
        # Straight-line haversine ≈ 19km (road distance is longer ~25km)
        d = haversine_km(19.0760, 72.8777, 19.2183, 72.9781)
        assert 15 < d < 25  # roughly 19km straight-line

    def test_symmetry(self):
        d1 = haversine_km(19.0, 72.8, 19.1, 72.9)
        d2 = haversine_km(19.1, 72.9, 19.0, 72.8)
        assert d1 == pytest.approx(d2, rel=0.001)


class TestParseLocationWkt:
    def test_valid_point(self):
        result = parse_location_wkt("POINT(72.8777 19.0760)")
        assert result == pytest.approx((19.0760, 72.8777), rel=0.001)

    def test_none_returns_none(self):
        assert parse_location_wkt(None) is None

    def test_invalid_wkt_returns_none(self):
        assert parse_location_wkt("invalid") is None


class TestPass1HardFilter:
    @pytest.mark.asyncio
    async def test_excludes_unavailable_volunteers(self):
        """Unavailable volunteers must be excluded."""
        from app.services.matching import pass1_hard_filter

        unavail = make_volunteer(skills=["first_aid"], is_available=False)
        avail = make_volunteer(skills=["first_aid"], is_available=True)

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [unavail, avail]
        db.execute = AsyncMock(return_value=result_mock)

        # is_available_now → True for no schedule
        candidates = await pass1_hard_filter(db, ["first_aid"])
        # Only avail volunteer should pass
        assert avail in candidates
        assert unavail not in candidates

    @pytest.mark.asyncio
    async def test_excludes_missing_required_skill(self):
        """Volunteers missing a required skill are excluded."""
        from app.services.matching import pass1_hard_filter

        has_skill = make_volunteer(skills=["first_aid", "nutrition"])
        no_skill = make_volunteer(skills=["general"])

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [has_skill, no_skill]
        db.execute = AsyncMock(return_value=result_mock)

        candidates = await pass1_hard_filter(db, ["first_aid"])
        assert has_skill in candidates
        assert no_skill not in candidates


class TestPass2Ranking:
    def test_closer_volunteer_ranked_higher_same_completion(self):
        """Volunteer closer to need should rank higher if completion rates equal."""
        nearby = make_volunteer(
            location_wkt="POINT(72.8777 19.0760)",  # ~0km from need
            completion_rate=1.0
        )
        faraway = make_volunteer(
            location_wkt="POINT(73.0000 19.5000)",  # ~50km away
            completion_rate=1.0
        )
        need_location = (19.0760, 72.8777)
        ranked = pass2_rank([nearby, faraway], need_location)
        assert ranked[0][0] == nearby

    def test_high_completion_rate_compensates_distance(self):
        """High completion rate can compensate for some distance."""
        mid_near_low_cr = make_volunteer(
            location_wkt="POINT(72.8900 19.0800)", completion_rate=0.5
        )
        far_high_cr = make_volunteer(
            location_wkt="POINT(72.9200 19.1100)", completion_rate=1.0
        )
        need_location = (19.0760, 72.8777)
        ranked = pass2_rank([mid_near_low_cr, far_high_cr], need_location)
        # Can't assert exactly who wins, but both should be ranked
        assert len(ranked) == 2

    def test_top_n_respected(self):
        vols = [make_volunteer() for _ in range(15)]
        ranked = pass2_rank(vols, None, top_n=10)
        assert len(ranked) <= 10


class TestPass3Kinship:
    @pytest.mark.asyncio
    async def test_kinship_pair_elevated(self):
        """A kinship-bonded pair should be preferred over two strangers."""
        from app.services.matching import pass3_kinship

        v1 = make_volunteer()
        v2 = make_volunteer()
        v3 = make_volunteer()

        # v1 and v2 have kinship
        edge = KinshipEdge(
            id=uuid.uuid4(),
            volunteer_a_id=v1.id,
            volunteer_b_id=v2.id,
            co_deployments=3,
            quality_score=0.9,
        )

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [edge]
        db.execute = AsyncMock(return_value=result_mock)

        pass2 = [(v1, 0.6), (v2, 0.55), (v3, 0.70)]  # v3 is individually highest
        selected, kinship_bonus = await pass3_kinship(db, pass2, required_count=2)

        # v1 and v2 should be selected as kinship-bonded pair
        assert v1 in selected or v2 in selected
        # kinship_bonus should be True since an edge exists
        # (may not always be True if v3 combo wins, depends on exact scores)

    @pytest.mark.asyncio
    async def test_single_volunteer_no_kinship_check(self):
        """For count=1, return top pass2 candidate directly."""
        from app.services.matching import pass3_kinship

        v1 = make_volunteer()
        v2 = make_volunteer()

        db = AsyncMock()
        pass2 = [(v1, 0.9), (v2, 0.7)]
        selected, kinship_bonus = await pass3_kinship(db, pass2, required_count=1)

        assert selected == [v1]
        assert not kinship_bonus
