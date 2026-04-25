"""
Nightly Decay Job — runs at 02:00 UTC daily.
Recalculates T scores and priority scores for all active needs.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.need import Need
from app.models.signal import Signal
from app.models.reporter import Reporter
from app.services.decay import compute_t_score, should_trigger_reverification, should_archive, get_effective_lambda
from app.services.scoring import compute_all_scores

logger = logging.getLogger(__name__)


async def run_nightly_decay(db: AsyncSession) -> None:
    """Recalculate T score and priority for all active needs."""
    logger.info("Running nightly decay job")
    now = datetime.now(timezone.utc)

    stmt = select(Need).where(Need.status == "active")
    result = await db.execute(stmt)
    needs = result.scalars().all()

    reverification_needed = []
    archived_count = 0
    updated_count = 0

    for need in needs:
        # Get dominant reporter trust score via signals
        stmt_signals = select(Signal).where(
            Signal.corroboration_id == need.id,
            Signal.reporter_id.is_not(None)
        ).limit(1)
        sig_result = await db.execute(stmt_signals)
        signal = sig_result.scalar_one_or_none()

        trust_score = 0.65
        if signal and signal.reporter_id:
            reporter = await db.get(Reporter, signal.reporter_id)
            if reporter:
                trust_score = reporter.trust_score

        # Compute new T score
        t_new = compute_t_score(
            need_category=need.need_category,
            last_corroborated=need.last_corroborated,
            trust_score=trust_score,
            reference_time=now,
        )
        lambda_per_hour = get_effective_lambda(need.need_category, trust_score)

        need.t_score = t_new
        need.lambda_per_hour = lambda_per_hour

        # Recompute urgencies
        stmt_urgencies = select(Signal.urgency).where(
            Signal.corroboration_id == need.id,
            Signal.urgency.is_not(None)
        )
        urg_result = await db.execute(stmt_urgencies)
        urgencies = [row[0] for row in urg_result.fetchall()]

        scores = compute_all_scores(
            signal_count=need.source_count,
            urgencies=urgencies or [3],
            need_category=need.need_category,
            c_score=need.c_score or 0.5,
            t_score=t_new,
            existing_g=need.g_score,
        )
        need.priority_score = scores.priority_score
        need.f_score = scores.f_score
        need.u_score = scores.u_score
        need.updated_at = now

        # Check thresholds
        if should_archive(t_new):
            # Archive if T < 0.05
            need.status = "archived"
            archived_count += 1
            logger.info(f"Archived need {need.id} (T={t_new:.3f})")
        elif should_trigger_reverification(t_new):
            reverification_needed.append(need)

        updated_count += 1

    await db.commit()
    logger.info(
        f"Nightly decay: updated={updated_count}, "
        f"reverification_needed={len(reverification_needed)}, "
        f"archived={archived_count}"
    )

    return reverification_needed
