"""
Ingestion Service — normalize all 5 incoming channels into Signal records.
Channels: whatsapp | ocr | app | csv | debrief
"""
import csv
import io
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.signal import Signal
from app.models.reporter import Reporter
from app.services.nlp_classifier import classify_report
from app.services.triangulation import process_signal
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def get_or_create_reporter(db: AsyncSession, phone: str, name: str | None = None) -> Reporter:
    """Get existing reporter by phone or create a new one."""
    stmt = select(Reporter).where(Reporter.phone == phone)
    result = await db.execute(stmt)
    reporter = result.scalar_one_or_none()

    if not reporter:
        reporter = Reporter(phone=phone, name=name)
        db.add(reporter)
        await db.flush()

    return reporter


async def ingest_whatsapp(
    db: AsyncSession,
    phone: str,
    raw_text: str,
    reporter_name: str | None = None,
) -> tuple[Signal, dict]:
    """Ingest a WhatsApp field report."""
    reporter = await get_or_create_reporter(db, phone, reporter_name)

    classification = await classify_report(raw_text)

    reporter.reports_filed += 1

    signal = Signal(
        reporter_id=reporter.id,
        source_channel="whatsapp",
        zone_id=classification.get("zone_id") or "Unknown",
        need_category=classification.get("need_category", "other"),
        urgency=classification.get("urgency"),
        population_est=classification.get("population_est"),
        raw_text=raw_text,
        confidence=classification.get("confidence", 0.0),
        state="watch",
        collected_at=datetime.now(timezone.utc),
    )
    db.add(signal)
    await db.flush()

    # Try triangulation
    need = await process_signal(db, signal)

    return signal, classification


async def ingest_ocr_image(
    db: AsyncSession,
    image_bytes: bytes,
    reporter_id: str | None = None,
    zone_hint: str | None = None,
) -> tuple[Signal, dict]:
    """Ingest an image via OCR then classify."""
    from app.services.ocr import extract_text_from_image
    raw_text = await extract_text_from_image(image_bytes)
    if not raw_text:
        raw_text = "[OCR: no text extracted]"

    classification = await classify_report(raw_text)
    if zone_hint and not classification.get("zone_id"):
        classification["zone_id"] = zone_hint

    signal = Signal(
        reporter_id=reporter_id,
        source_channel="ocr",
        zone_id=classification.get("zone_id") or zone_hint or "Unknown",
        need_category=classification.get("need_category", "other"),
        urgency=classification.get("urgency"),
        population_est=classification.get("population_est"),
        raw_text=raw_text,
        confidence=classification.get("confidence", 0.0),
        state="watch",
        collected_at=datetime.now(timezone.utc),
    )
    db.add(signal)
    await db.flush()

    need = await process_signal(db, signal)

    return signal, classification


async def ingest_csv(
    db: AsyncSession,
    csv_content: str,
) -> list[Signal]:
    """Batch-ingest signals from CSV content.
    Expected columns: zone_id, need_category, urgency, population_est, raw_text, reporter_phone, collected_at
    """
    signals = []
    reader = csv.DictReader(io.StringIO(csv_content))

    for row in reader:
        reporter = None
        phone = row.get("reporter_phone", "").strip()
        if phone:
            reporter = await get_or_create_reporter(db, phone)

        try:
            collected_at = datetime.fromisoformat(row.get("collected_at", "").strip())
        except Exception:
            collected_at = datetime.now(timezone.utc)

        urgency = None
        try:
            urgency = int(row.get("urgency", 3))
        except Exception:
            urgency = 3

        signal = Signal(
            reporter_id=reporter.id if reporter else None,
            source_channel="csv",
            zone_id=row.get("zone_id", "Unknown").strip(),
            need_category=row.get("need_category", "other").strip(),
            urgency=urgency,
            population_est=int(row["population_est"]) if row.get("population_est") else None,
            raw_text=row.get("raw_text", "").strip() or None,
            confidence=1.0,  # CSV = coordinator-confirmed
            state="watch",
            collected_at=collected_at,
        )
        db.add(signal)
        await db.flush()
        await process_signal(db, signal)
        signals.append(signal)

    return signals


async def ingest_manual(
    db: AsyncSession,
    zone_id: str,
    need_category: str,
    urgency: int,
    population_est: int | None,
    raw_text: str | None,
    reporter_id: str | None = None,
    source_channel: str = "app",
    confidence: float = 1.0,
    classifier: str = "manual",
) -> Signal:
    """Direct manual ingest via the REST API."""
    signal = Signal(
        reporter_id=reporter_id,
        source_channel=source_channel,
        zone_id=zone_id,
        need_category=need_category,
        urgency=urgency,
        population_est=population_est,
        raw_text=raw_text,
        confidence=confidence,
        state="watch",
        collected_at=datetime.now(timezone.utc),
    )
    # Attach classifier as a transient attribute for the API response
    signal.__dict__["classifier"] = classifier
    db.add(signal)
    await db.flush()
    await process_signal(db, signal)
    return signal
