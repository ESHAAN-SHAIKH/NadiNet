"""
Reporters API — trust scores and management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from app.database import get_db
from app.models.reporter import Reporter
from app.schemas import ReporterOut, ReporterUpdate
from app.services.decay import update_reporter_decay_modifier

router = APIRouter()


@router.get("/reporters", response_model=List[ReporterOut])
async def list_reporters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Reporter).order_by(Reporter.trust_score.desc()))
    return result.scalars().all()


@router.get("/reporters/{reporter_id}", response_model=ReporterOut)
async def get_reporter(reporter_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    reporter = await db.get(Reporter, reporter_id)
    if not reporter:
        raise HTTPException(status_code=404, detail="Reporter not found")
    return reporter


@router.patch("/reporters/{reporter_id}/trust", response_model=ReporterOut)
async def update_reporter_trust(
    reporter_id: uuid.UUID,
    payload: ReporterUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Manual trust score adjustment with required justification."""
    if payload.trust_score is not None and not payload.justification:
        raise HTTPException(status_code=400, detail="Justification required for trust score adjustment")

    reporter = await db.get(Reporter, reporter_id)
    if not reporter:
        raise HTTPException(status_code=404, detail="Reporter not found")

    if payload.trust_score is not None:
        reporter.trust_score = max(0.0, min(1.0, payload.trust_score))
        reporter.decay_modifier = update_reporter_decay_modifier(reporter.trust_score)

    if payload.name is not None:
        reporter.name = payload.name

    await db.commit()
    return reporter
