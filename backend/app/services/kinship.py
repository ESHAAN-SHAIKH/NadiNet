"""
Kinship Graph Service — manages co-deployment edges and reporter trust updates.
"""
import logging
from datetime import datetime, timezone
from itertools import combinations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.kinship import KinshipEdge
from app.models.task import Task
from app.models.volunteer import Volunteer
from app.models.reporter import Reporter
from app.models.signal import Signal
from app.models.need import Need
from app.services.decay import update_reporter_decay_modifier

logger = logging.getLogger(__name__)

OUTCOME_QUALITY = {
    "resolved": 1.0,
    "partial": 0.6,
    "unresolved": 0.0,
}


async def update_kinship_edges(
    db: AsyncSession,
    task_id: str,
    resolution: str,
) -> None:
    """
    On debrief: update kinship edges for all pairs of co-deployed volunteers.
    """
    # Find all tasks for the same need that were accepted or complete
    task = await db.get(Task, task_id)
    if not task:
        return

    stmt = select(Task).where(
        and_(
            Task.need_id == task.need_id,
            Task.status.in_(["accepted", "complete"]),
        )
    )
    result = await db.execute(stmt)
    related_tasks = result.scalars().all()

    volunteer_ids = list({t.volunteer_id for t in related_tasks})
    if len(volunteer_ids) < 2:
        return

    outcome_quality = OUTCOME_QUALITY.get(resolution, 0.0)
    now = datetime.now(timezone.utc)

    for v_a_id, v_b_id in combinations(volunteer_ids, 2):
        # Canonical ordering (smaller UUID first)
        if str(v_a_id) > str(v_b_id):
            v_a_id, v_b_id = v_b_id, v_a_id

        stmt_edge = select(KinshipEdge).where(
            and_(
                KinshipEdge.volunteer_a_id == v_a_id,
                KinshipEdge.volunteer_b_id == v_b_id,
            )
        )
        result_edge = await db.execute(stmt_edge)
        edge = result_edge.scalar_one_or_none()

        if edge:
            # Rolling average quality
            new_quality = (
                (edge.quality_score * edge.co_deployments + outcome_quality)
                / (edge.co_deployments + 1)
            )
            edge.co_deployments += 1
            edge.quality_score = round(new_quality, 4)
            edge.last_deployed = now
        else:
            edge = KinshipEdge(
                volunteer_a_id=v_a_id,
                volunteer_b_id=v_b_id,
                co_deployments=1,
                quality_score=outcome_quality,
                last_deployed=now,
            )
            db.add(edge)


async def update_reporter_trust(
    db: AsyncSession,
    need_id: str,
    resolution: str,
) -> None:
    """
    Update reporter trust scores based on debrief resolution.
    """
    # Find signals linked to this need
    stmt = select(Signal).where(Signal.corroboration_id == need_id)
    result = await db.execute(stmt)
    signals = result.scalars().all()

    reporter_ids = {s.reporter_id for s in signals if s.reporter_id}

    for reporter_id in reporter_ids:
        reporter = await db.get(Reporter, reporter_id)
        if not reporter:
            continue

        if resolution == "resolved":
            reporter.reports_verified += 1

        # Bayesian update: trust = verified / filed
        if reporter.reports_filed > 0:
            reporter.trust_score = min(0.99, reporter.reports_verified / reporter.reports_filed)

        # Update decay modifier
        reporter.decay_modifier = update_reporter_decay_modifier(reporter.trust_score)
