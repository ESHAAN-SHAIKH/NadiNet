"""
Needs API — GET/POST/PATCH /api/v1/needs
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
import uuid
from app.database import get_db
from app.models.need import Need
from app.models.signal import Signal
from app.schemas import NeedOut, NeedUpdate, NeedPromote
from app.services.scoring import compute_all_scores
from app.services.decay import get_effective_lambda
from datetime import datetime, timezone

router = APIRouter()


@router.get("/needs", response_model=List[NeedOut])
async def list_needs(
    status: Optional[str] = "active",
    zone_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List needs sorted by priority_score descending."""
    stmt = select(Need).where(Need.status == status)
    if zone_id:
        stmt = stmt.where(Need.zone_id == zone_id)
    stmt = stmt.order_by(desc(Need.priority_score)).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/needs/{need_id}", response_model=NeedOut)
async def get_need(need_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    need = await db.get(Need, need_id)
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")
    return need


@router.get("/needs/{need_id}/signals")
async def get_need_signals(need_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all corroborating signals for a need."""
    need = await db.get(Need, need_id)
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")
    stmt = select(Signal).where(Signal.corroboration_id == need_id)
    result = await db.execute(stmt)
    signals = result.scalars().all()
    return signals


@router.get("/needs/{need_id}/candidates")
async def get_need_candidates(
    need_id: uuid.UUID,
    skills: Optional[str] = None,
    count: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Run 3-pass matching and return ranked volunteer candidates."""
    from app.services.matching import find_candidates, pass2_rank
    from app.models.volunteer import Volunteer

    need = await db.get(Need, need_id)
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    required_skills = [s.strip() for s in skills.split(",")] if skills else []

    result = await find_candidates(db, need, required_skills, count)

    # candidates is list[tuple[Volunteer, float]]
    candidates_out = []
    for v, p2_score in result["candidates"][:10]:
        candidates_out.append({
            "id": str(v.id),
            "name": v.name,
            "phone": "***" + v.phone[-4:] if len(v.phone) >= 4 else v.phone,
            "skills": v.skills,
            "zone_id": v.zone_id,
            "trust_score": v.trust_score,
            "completion_rate": v.completion_rate,
            "is_available": v.is_available,
            "pass2_score": round(p2_score, 3),
            "is_recommended": v in result["recommended"],
        })

    return {
        "need_id": str(need_id),
        "candidates": candidates_out,
        "recommended_ids": [str(v.id) for v in result["recommended"]],
        "kinship_bonus": result["kinship_bonus"],
        "pool_size": result["pool_size"],
    }


@router.post("/needs/{need_id}/promote")
async def promote_need(
    need_id: uuid.UUID,
    payload: NeedPromote,
    db: AsyncSession = Depends(get_db),
):
    """Manual coordinator promotion of a watch-state signal into an active Need."""
    from app.services.triangulation import manually_promote_signal

    # Find a watch-state signal in this zone/category
    stmt = select(Signal).where(
        Signal.corroboration_id == None,
        Signal.state == "watch",
    ).limit(1)
    result = await db.execute(stmt)
    signal = result.scalar_one_or_none()

    if signal:
        need = await manually_promote_signal(db, signal)
        await db.commit()
        return {"need_id": str(need.id), "promoted": True}

    # Check if need exists
    need = await db.get(Need, need_id)
    if need:
        return {"need_id": str(need_id), "promoted": False, "reason": "Already active"}

    raise HTTPException(status_code=404, detail="No promotable signal found")


@router.patch("/needs/{need_id}", response_model=NeedOut)
async def update_need(
    need_id: uuid.UUID,
    payload: NeedUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update G score or status of a need."""
    need = await db.get(Need, need_id)
    if not need:
        raise HTTPException(status_code=404, detail="Need not found")

    if payload.g_score is not None:
        need.g_score = payload.g_score
        # Rescore
        stmt_urg = select(Signal.urgency).where(Signal.corroboration_id == need_id)
        urg_result = await db.execute(stmt_urg)
        urgencies = [r[0] for r in urg_result.fetchall() if r[0]]
        scores = compute_all_scores(
            signal_count=need.source_count,
            urgencies=urgencies or [3],
            need_category=need.need_category,
            c_score=need.c_score or 0.5,
            t_score=need.t_score or 1.0,
            existing_g=need.g_score,
        )
        need.priority_score = scores.priority_score

    if payload.status is not None:
        need.status = payload.status

    need.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return need
