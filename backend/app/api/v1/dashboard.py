"""
Dashboard API — aggregated stats for frontend metric cards and visualizations.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.models.need import Need
from app.models.signal import Signal
from app.models.volunteer import Volunteer
from app.models.task import Task
from app.models.debrief import Debrief
from app.models.reporter import Reporter
from app.models.kinship import KinshipEdge

router = APIRouter()


@router.get("/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate metrics for the 4 metric cards."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Active needs
    stmt = select(func.count()).select_from(Need).where(Need.status == "active")
    total_active_needs = (await db.execute(stmt)).scalar() or 0

    # Watch signals
    stmt = select(func.count()).select_from(Signal).where(Signal.state == "watch")
    total_watch = (await db.execute(stmt)).scalar() or 0

    # Volunteers
    stmt_all = select(func.count()).select_from(Volunteer)
    stmt_avail = select(func.count()).select_from(Volunteer).where(Volunteer.is_available == True)
    total_vols = (await db.execute(stmt_all)).scalar() or 0
    avail_vols = (await db.execute(stmt_avail)).scalar() or 0

    # Kinship matches today (tasks with kinship_bonus dispatched today)
    stmt_kinship = select(func.count()).select_from(Task).where(
        and_(Task.kinship_bonus == True, Task.dispatched_at >= today_start)
    )
    kinship_today = (await db.execute(stmt_kinship)).scalar() or 0

    # Avg decay age (hours since last_corroborated for active needs)
    stmt_needs = select(Need).where(Need.status == "active")
    needs_result = await db.execute(stmt_needs)
    active_needs = needs_result.scalars().all()

    avg_decay_days = 0.0
    if active_needs:
        total_hours = sum(
            (now - (n.last_corroborated.replace(tzinfo=timezone.utc) if n.last_corroborated.tzinfo is None else n.last_corroborated)).total_seconds() / 3600
            for n in active_needs
        )
        avg_decay_days = round(total_hours / len(active_needs) / 24, 1)

    # Needs needing reverification (t_score < 0.2)
    stmt_rev = select(func.count()).select_from(Need).where(
        and_(Need.status == "active", Need.t_score < 0.20)
    )
    rev_needed = (await db.execute(stmt_rev)).scalar() or 0

    return {
        "total_active_needs": total_active_needs,
        "total_watch_signals": total_watch,
        "total_volunteers": total_vols,
        "available_volunteers": avail_vols,
        "kinship_matches_today": kinship_today,
        "avg_decay_age_days": avg_decay_days,
        "needs_needing_reverification": rev_needed,
    }


@router.get("/dashboard/heatmap")
async def get_heatmap(db: AsyncSession = Depends(get_db)):
    """Corroboration matrix: need_category × source_channel counts."""
    stmt = select(
        Signal.need_category,
        Signal.source_channel,
        func.count().label("count")
    ).group_by(Signal.need_category, Signal.source_channel)
    result = await db.execute(stmt)
    rows = result.fetchall()

    return [
        {"need_category": row[0], "source_channel": row[1], "count": row[2]}
        for row in rows
    ]


@router.get("/dashboard/signal-log")
async def get_signal_log(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Chronological audit trail of all system events."""
    events = []

    # Recent signals
    stmt = select(Signal).order_by(Signal.synced_at.desc()).limit(limit // 3)
    result = await db.execute(stmt)
    signals = result.scalars().all()
    for s in signals:
        events.append({
            "id": str(s.id),
            "event_type": "SIGNAL_INGESTED",
            "timestamp": s.synced_at,
            "description": f"Signal from {s.source_channel}: {s.need_category} in {s.zone_id}",
            "metadata": {"zone_id": s.zone_id, "channel": s.source_channel, "state": s.state},
        })

    # Recent tasks
    stmt = select(Task).order_by(Task.dispatched_at.desc()).limit(limit // 3)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    for t in tasks:
        event_type = {
            "pending": "TASK_DISPATCHED",
            "accepted": "TASK_ACCEPTED",
            "declined": "TASK_DECLINED",
            "complete": "DEBRIEF_RECEIVED",
        }.get(t.status, "TASK_DISPATCHED")

        events.append({
            "id": str(t.id),
            "event_type": event_type,
            "timestamp": t.dispatched_at,
            "description": f"Task {t.status} for volunteer {t.volunteer_id}",
            "metadata": {"need_id": str(t.need_id), "volunteer_id": str(t.volunteer_id), "status": t.status},
        })

    # Recent needs (corroborated)
    stmt = select(Need).order_by(Need.created_at.desc()).limit(limit // 3)
    result = await db.execute(stmt)
    needs = result.scalars().all()
    for n in needs:
        events.append({
            "id": str(n.id),
            "event_type": "NEED_CORROBORATED" if n.status == "active" else "NEED_ARCHIVED",
            "timestamp": n.created_at,
            "description": f"Need corroborated: {n.need_category} in {n.zone_id} (score: {n.priority_score})",
            "metadata": {"zone_id": n.zone_id, "category": n.need_category, "score": n.priority_score},
        })

    # Sort chronologically
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:limit]


@router.get("/dashboard/kinship")
async def get_kinship_graph(db: AsyncSession = Depends(get_db)):
    """Graph nodes (volunteers) and edges (kinship) for visualization."""
    stmt_vols = select(Volunteer).limit(100)
    result = await db.execute(stmt_vols)
    volunteers = result.scalars().all()

    stmt_edges = select(KinshipEdge).where(KinshipEdge.co_deployments >= 1).limit(200)
    result = await db.execute(stmt_edges)
    edges = result.scalars().all()

    nodes = [
        {
            "id": str(v.id),
            "name": v.name,
            "initials": "".join(w[0].upper() for w in v.name.split()[:2]),
            "zone_id": v.zone_id,
            "skills": v.skills or [],
            "trust_score": v.trust_score,
            "completion_rate": v.completion_rate,
            "is_available": v.is_available,
        }
        for v in volunteers
    ]

    edge_list = [
        {
            "id": str(e.id),
            "source": str(e.volunteer_a_id),
            "target": str(e.volunteer_b_id),
            "co_deployments": e.co_deployments,
            "quality_score": e.quality_score,
            "last_deployed": e.last_deployed,
        }
        for e in edges
    ]

    return {"nodes": nodes, "edges": edge_list}
