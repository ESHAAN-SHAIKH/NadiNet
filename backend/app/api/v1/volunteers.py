"""
Volunteers API — CRUD + availability
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import uuid
from app.database import get_db
from app.models.volunteer import Volunteer
from app.schemas import VolunteerCreate, VolunteerUpdate, VolunteerOut

router = APIRouter()


@router.get("/volunteers", response_model=List[VolunteerOut])
async def list_volunteers(
    is_available: Optional[bool] = None,
    zone_id: Optional[str] = None,
    skill: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Volunteer)
    if is_available is not None:
        stmt = stmt.where(Volunteer.is_available == is_available)
    if zone_id:
        stmt = stmt.where(Volunteer.zone_id == zone_id)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    volunteers = result.scalars().all()

    if skill:
        volunteers = [v for v in volunteers if skill in (v.skills or [])]
    return volunteers


@router.get("/volunteers/{volunteer_id}", response_model=VolunteerOut)
async def get_volunteer(volunteer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    v = await db.get(Volunteer, volunteer_id)
    if not v:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    return v


@router.post("/volunteers", response_model=VolunteerOut, status_code=201)
async def create_volunteer(
    payload: VolunteerCreate,
    db: AsyncSession = Depends(get_db),
):
    v = Volunteer(**payload.model_dump())
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return v


@router.patch("/volunteers/{volunteer_id}", response_model=VolunteerOut)
async def update_volunteer(
    volunteer_id: uuid.UUID,
    payload: VolunteerUpdate,
    db: AsyncSession = Depends(get_db),
):
    v = await db.get(Volunteer, volunteer_id)
    if not v:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(v, field, value)

    await db.commit()
    await db.refresh(v)
    return v


@router.patch("/volunteers/{volunteer_id}/availability")
async def update_availability(
    volunteer_id: uuid.UUID,
    is_available: bool,
    db: AsyncSession = Depends(get_db),
):
    v = await db.get(Volunteer, volunteer_id)
    if not v:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    v.is_available = is_available
    await db.commit()
    return {"volunteer_id": str(volunteer_id), "is_available": is_available}
