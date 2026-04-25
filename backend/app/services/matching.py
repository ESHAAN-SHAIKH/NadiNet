"""
find_candidates return format was passing the wrong structure. Fixed to return
list of (Volunteer, score) tuples cleanly so the API route can unpack them.
Also adds cascade logic: on decline, re-run dispatch for next candidate.
"""
import logging
import math
from datetime import datetime, timezone
from itertools import combinations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.volunteer import Volunteer
from app.models.need import Need
from app.models.kinship import KinshipEdge

logger = logging.getLogger(__name__)

MAX_RADIUS_KM = 20.0


def is_available_now(schedule: dict | None) -> bool:
    """Check if a volunteer is currently available based on their schedule."""
    if not schedule:
        return True  # No schedule = always available

    now = datetime.now(timezone.utc)
    day_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    day_key = day_map.get(now.weekday(), "mon")
    day_slots = schedule.get(day_key, [])

    if not day_slots:
        return False

    current_time = now.strftime("%H:%M")
    for slot in day_slots:
        start = slot.get("start", "00:00")
        end = slot.get("end", "23:59")
        if start <= current_time <= end:
            return True
    return False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_location_wkt(wkt: str | None) -> tuple[float, float] | None:
    """Parse POINT(lon lat) WKT to (lat, lon) tuple."""
    if not wkt:
        return None
    try:
        coords = wkt.replace("POINT(", "").replace(")", "").strip().split()
        lon, lat = float(coords[0]), float(coords[1])
        return (lat, lon)
    except Exception:
        return None


async def pass1_hard_filter(
    db: AsyncSession,
    required_skills: list[str],
) -> list[Volunteer]:
    """
    Pass 1: Filter volunteers who have ALL required skills, are is_available,
    and are within their current availability schedule slot.
    """
    stmt = select(Volunteer).where(Volunteer.is_available == True)
    result = await db.execute(stmt)
    candidates = result.scalars().all()

    filtered = []
    for v in candidates:
        if not v.is_available:
            continue
        v_skills = set(v.skills or [])
        req_skills = set(required_skills)
        if req_skills.issubset(v_skills) and is_available_now(v.availability_schedule):
            filtered.append(v)

    return filtered


def pass2_rank(
    candidates: list[Volunteer],
    need_location: tuple[float, float] | None,
    top_n: int = 10,
) -> list[tuple[Volunteer, float]]:
    """
    Pass 2: Rank by proximity + completion_rate.
    proximity_score = max(0, 1 - distance_km / 20)
    pass2_score = (proximity × 0.6) + (completion_rate × 0.4)
    """
    scored = []
    for v in candidates:
        if need_location and v.location_wkt:
            v_loc = parse_location_wkt(v.location_wkt)
            if v_loc:
                dist = haversine_km(v_loc[0], v_loc[1], need_location[0], need_location[1])
                proximity = max(0.0, 1.0 - (dist / MAX_RADIUS_KM))
            else:
                proximity = 0.5
        else:
            proximity = 0.5

        history_score = v.completion_rate
        pass2_score = (proximity * 0.6) + (history_score * 0.4)
        scored.append((v, pass2_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


async def pass3_kinship(
    db: AsyncSession,
    pass2_results: list[tuple[Volunteer, float]],
    required_count: int,
) -> tuple[list[Volunteer], bool]:
    """
    Pass 3: Kinship graph optimization.
    For required_count > 1, evaluate all combos of candidates and pick the
    team with (mean pass2_score + kinship_bonus) highest composite.
    Returns (selected_volunteers, kinship_bonus_applied).
    """
    if required_count == 1:
        if pass2_results:
            return [pass2_results[0][0]], False
        return [], False

    volunteers = [v for v, _ in pass2_results]
    scores_map = {v.id: s for v, s in pass2_results}

    v_ids = [v.id for v in volunteers]
    stmt = select(KinshipEdge).where(
        and_(
            KinshipEdge.volunteer_a_id.in_(v_ids),
            KinshipEdge.volunteer_b_id.in_(v_ids),
        )
    )
    result = await db.execute(stmt)
    edges = result.scalars().all()

    edge_map: dict[tuple, KinshipEdge] = {}
    for edge in edges:
        edge_map[(edge.volunteer_a_id, edge.volunteer_b_id)] = edge
        edge_map[(edge.volunteer_b_id, edge.volunteer_a_id)] = edge

    best_combo: list[Volunteer] | None = None
    best_score = -1.0
    best_kinship_bonus = 0.0

    for combo in combinations(range(min(len(volunteers), 10)), required_count):
        selected = [volunteers[i] for i in combo]
        mean_p2 = sum(scores_map[v.id] for v in selected) / required_count
        kinship_bonus = 0.0

        for i in range(len(selected)):
            for j in range(i + 1, len(selected)):
                edge = edge_map.get((selected[i].id, selected[j].id))
                if edge:
                    kinship_bonus += edge.quality_score * edge.co_deployments * 0.1

        composite = mean_p2 + kinship_bonus
        if composite > best_score:
            best_score = composite
            best_combo = selected
            best_kinship_bonus = kinship_bonus

    if best_combo is None:
        best_combo = volunteers[:required_count]
        best_kinship_bonus = 0.0

    return best_combo, best_kinship_bonus > 0


async def cascade_to_next_candidate(
    db: AsyncSession,
    need: Need,
    declined_volunteer_id,
    required_skills: list[str],
) -> None:
    """
    When a volunteer declines, automatically dispatch to the next best candidate.
    """
    from app.models.task import Task
    from app.services.whatsapp import send_dispatch_message

    pool = await pass1_hard_filter(db, required_skills)
    # Exclude declined volunteer
    pool = [v for v in pool if v.id != declined_volunteer_id]
    ranked = pass2_rank(pool, parse_location_wkt(need.location_wkt))

    if not ranked:
        logger.warning(f"No more candidates for need {need.id} after cascade")
        return

    next_volunteer = ranked[0][0]

    task = Task(
        need_id=need.id,
        volunteer_id=next_volunteer.id,
        status="pending",
        dispatched_at=datetime.now(timezone.utc),
        kinship_bonus=False,
    )
    db.add(task)
    await db.flush()

    await send_dispatch_message(
        volunteer=next_volunteer,
        need_category=need.need_category,
        zone_id=need.zone_id,
        task_id=str(task.id),
        db=db,
    )
    logger.info(f"Cascaded dispatch to {next_volunteer.name} for need {need.id}")


async def find_candidates(
    db: AsyncSession,
    need: Need,
    required_skills: list[str],
    required_count: int = 1,
) -> dict:
    """
    Run all 3 passes and return ranked candidates info as structured dict.
    'candidates' is a list of (Volunteer, pass2_score) tuples for the API route.
    """
    need_location = parse_location_wkt(need.location_wkt)

    pool = await pass1_hard_filter(db, required_skills)
    ranked = pass2_rank(pool, need_location)
    selected, kinship_bonus = await pass3_kinship(db, ranked, required_count)

    return {
        "candidates": ranked,          # list[tuple[Volunteer, float]]
        "recommended": selected,        # list[Volunteer]
        "kinship_bonus": kinship_bonus,
        "pool_size": len(pool),
    }
