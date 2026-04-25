"""
Ingest API — POST /api/v1/ingest
Accepts CSV upload or JSON push to create signals.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import IngestRequest, SignalOut
from app.services.ingestion import ingest_manual, ingest_csv, ingest_ocr_image
from datetime import datetime, timezone

router = APIRouter()


@router.post("/ingest", response_model=SignalOut)
async def ingest_signal(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manual signal ingestion via REST (JSON push). Auto-classifies raw_text if need_category is omitted."""
    from app.services.nlp_classifier import classify_report

    reporter_id = None
    if payload.reporter_phone:
        from app.services.ingestion import get_or_create_reporter
        reporter = await get_or_create_reporter(db, payload.reporter_phone)
        reporter_id = reporter.id

    # Auto-classify from raw_text when need_category not provided
    classification = {}
    if not payload.need_category and payload.raw_text:
        classification = await classify_report(payload.raw_text)

    need_category = payload.need_category or classification.get("need_category", "other")
    urgency = payload.urgency or classification.get("urgency", 3)
    confidence = classification.get("confidence", 1.0) if classification else 1.0
    classifier = classification.get("classifier", "manual") if classification else "manual"

    signal = await ingest_manual(
        db=db,
        zone_id=payload.zone_id,
        need_category=need_category,
        urgency=urgency,
        population_est=payload.population_est,
        raw_text=payload.raw_text,
        reporter_id=reporter_id,
        source_channel=payload.source_channel,
        confidence=confidence,
        classifier=classifier,
    )
    await db.commit()
    return signal



@router.post("/ingest/csv")
async def ingest_csv_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Batch ingest from CSV file upload."""
    content = await file.read()
    csv_text = content.decode("utf-8-sig")
    signals = await ingest_csv(db, csv_text)
    await db.commit()
    return {"ingested": len(signals), "signal_ids": [str(s.id) for s in signals]}


@router.post("/ingest/ocr")
async def ingest_ocr_upload(
    file: UploadFile = File(...),
    zone_hint: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Ingest image, OCR → classify → create signal."""
    image_bytes = await file.read()
    signal, classification = await ingest_ocr_image(db, image_bytes, zone_hint=zone_hint)
    await db.commit()
    return {
        "signal_id": str(signal.id),
        "classification": classification,
        "state": signal.state,
    }
