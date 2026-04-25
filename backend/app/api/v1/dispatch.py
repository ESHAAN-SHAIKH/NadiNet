"""
Dispatch API — POST /api/v1/dispatch
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.database import get_db
from app.models.task import Task
from app.models.need import Need
from app.models.volunteer import Volunteer
from app.schemas import DispatchRequest, TaskOut
from app.services.whatsapp import send_dispatch_message
from datetime import datetime, timezone

router = APIRouter()


@router.post("/dispatch", response_model=list[TaskOut])
async def dispatch_volunteers(
    payload: DispatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create tasks for selected volunteers and send WhatsApp notifications."""
    need = await db.get(Need, payload.need_id)
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    tasks = []
    for vol_id in payload.volunteer_ids:
        volunteer = await db.get(Volunteer, vol_id)
        if not volunteer:
            continue

        task = Task(
            need_id=need.id,
            volunteer_id=volunteer.id,
            status="pending",
            kinship_bonus=payload.send_whatsapp and len(payload.volunteer_ids) > 1,
            dispatched_at=datetime.now(timezone.utc),
        )
        db.add(task)
        await db.flush()
        tasks.append(task)

        if payload.send_whatsapp:
            await send_dispatch_message(
                volunteer=volunteer,
                need_category=need.need_category,
                zone_id=need.zone_id,
                task_id=str(task.id),
                db=db,
            )

    await db.commit()
    return tasks


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.dispatched_at.desc()).limit(100)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/tasks/{task_id}/status", response_model=TaskOut)
async def update_task_status(
    task_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_status = payload.get("status")
    if new_status:
        task.status = new_status
        now = datetime.now(timezone.utc)
        if new_status == "accepted":
            task.accepted_at = now
        elif new_status == "complete":
            task.completed_at = now
        elif new_status == "declined":
            # Spec §6: On reply=NO or no reply, cascade to next candidate automatically
            need = await db.get(Need, task.need_id)
            if need:
                from app.services.matching import cascade_to_next_candidate
                await cascade_to_next_candidate(
                    db=db,
                    need=need,
                    declined_volunteer_id=task.volunteer_id,
                    required_skills=[],
                )

    await db.commit()
    return task
