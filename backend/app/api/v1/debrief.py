"""
Debrief API — POST /api/v1/debrief
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.database import get_db
from app.models.debrief import Debrief
from app.models.task import Task
from app.models.need import Need
from app.schemas import DebriefCreate, DebriefOut
from app.services.kinship import update_kinship_edges, update_reporter_trust
from app.services.scoring import compute_g_score, compute_all_scores
from app.models.signal import Signal
from datetime import datetime, timezone

router = APIRouter()


@router.post("/debrief", response_model=DebriefOut, status_code=201)
async def submit_debrief(
    payload: DebriefCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit post-task debrief, trigger scoring update and kinship update."""
    task = await db.get(Task, payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Auto-resolve need_id and volunteer_id from task if not supplied
    need_id = payload.need_id or task.need_id
    volunteer_id = payload.volunteer_id or task.volunteer_id

    need = await db.get(Need, need_id)
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    debrief = Debrief(
        task_id=payload.task_id,
        volunteer_id=volunteer_id,
        need_id=need_id,
        resolution=payload.resolution,
        people_helped=payload.people_helped,
        notes=payload.notes,
    )
    db.add(debrief)


    # Update task status
    task.status = "complete"
    task.completed_at = datetime.now(timezone.utc)

    # Update G score immediately (exception to nightly-only rule per spec)
    new_g = compute_g_score(need.g_score, payload.resolution)
    need.g_score = new_g

    # Rescore
    stmt_urg = select(Signal.urgency).where(Signal.corroboration_id == need.id)
    urg_result = await db.execute(stmt_urg)
    urgencies = [r[0] for r in urg_result.fetchall() if r[0]]

    scores = compute_all_scores(
        signal_count=need.source_count,
        urgencies=urgencies or [3],
        need_category=need.need_category,
        c_score=need.c_score or 0.5,
        t_score=need.t_score or 1.0,
        existing_g=new_g,
        resolution=payload.resolution,
    )
    need.priority_score = scores.priority_score
    need.updated_at = datetime.now(timezone.utc)

    if payload.resolution == "resolved":
        need.status = "resolved"

    await db.flush()

    # Update kinship edges and reporter trust
    await update_kinship_edges(db, str(payload.task_id), payload.resolution)
    await update_reporter_trust(db, str(need_id), payload.resolution)

    await db.commit()
    return debrief
