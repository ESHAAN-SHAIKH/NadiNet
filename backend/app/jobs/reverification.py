"""
Reverification Job — runs at 08:00 UTC daily.
Sends WhatsApp messages to reporters for needs with T < 0.20.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.need import Need
from app.models.signal import Signal
from app.models.reporter import Reporter
from app.services.decay import should_trigger_reverification
from app.services.whatsapp import send_reverification_message

logger = logging.getLogger(__name__)


async def run_reverification(db: AsyncSession) -> None:
    """Send reverification pings for needs with low T scores."""
    logger.info("Running reverification job")
    now = datetime.now(timezone.utc)

    # Find active needs that need reverification
    stmt = select(Need).where(
        and_(
            Need.status == "active",
            Need.t_score < 0.20,
        )
    )
    result = await db.execute(stmt)
    needs = result.scalars().all()

    sent_count = 0
    for need in needs:
        # Find the original reporter
        stmt_signal = select(Signal).where(
            and_(
                Signal.corroboration_id == need.id,
                Signal.reporter_id.is_not(None),
            )
        ).order_by(Signal.collected_at.asc()).limit(1)
        sig_result = await db.execute(stmt_signal)
        signal = sig_result.scalar_one_or_none()

        if not signal or not signal.reporter_id:
            continue

        reporter = await db.get(Reporter, signal.reporter_id)
        if not reporter or not reporter.phone:
            continue

        days_elapsed = int((now - need.last_corroborated).total_seconds() / 86400)

        await send_reverification_message(
            reporter=reporter,
            need_category=need.need_category,
            zone_id=need.zone_id,
            need_id=str(need.id),
            days_elapsed=days_elapsed,
            db=db,
        )
        sent_count += 1

    await db.commit()
    logger.info(f"Reverification: sent {sent_count} messages")
