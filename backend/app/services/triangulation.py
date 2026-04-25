"""
Triangulation Engine — corroboration state machine.
Determines when signals from multiple reporters constitute a corroborated Need.
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.signal import Signal
from app.models.need import Need
from app.models.reporter import Reporter
from app.services import scoring, decay

logger = logging.getLogger(__name__)

CORROBORATION_WINDOW_HOURS = 72


def compute_c_score(
    existing_signal: Signal,
    new_signal: Signal,
    existing_reporter: Reporter | None,
    new_reporter: Reporter | None,
) -> float:
    """
    Compute corroboration weight C:
    - source_diversity_bonus: +0.3 if different source_channel
    - temporal_proximity: 1.0 if same day, 0.7 if within 24h, 0.4 if within 72h
    - reporter_independence: 1.0 if different reporters, 0.3 if same reporter
    - geographic_precision: +0.2 if same "street block" (not implemented → 0)
    C = (sum) / 2.5, clamped to [0.0, 1.0]
    """
    # Source diversity
    source_diversity_bonus = 0.3 if existing_signal.source_channel != new_signal.source_channel else 0.0

    # Temporal proximity
    t1 = existing_signal.collected_at
    t2 = new_signal.collected_at
    if t1.tzinfo is None:
        t1 = t1.replace(tzinfo=timezone.utc)
    if t2.tzinfo is None:
        t2 = t2.replace(tzinfo=timezone.utc)
    hours_diff = abs((t2 - t1).total_seconds()) / 3600.0

    if t1.date() == t2.date():
        temporal_proximity = 1.0
    elif hours_diff <= 24:
        temporal_proximity = 0.7
    else:
        temporal_proximity = 0.4

    # Reporter independence
    same_reporter = (
        existing_signal.reporter_id is not None
        and existing_signal.reporter_id == new_signal.reporter_id
    )
    reporter_independence = 0.3 if same_reporter else 1.0

    # Geographic precision (street-level not tracked → 0)
    geographic_precision = 0.0

    raw_c = (source_diversity_bonus + temporal_proximity + reporter_independence + geographic_precision) / 2.5
    return max(0.0, min(1.0, raw_c))


async def process_signal(
    db: AsyncSession,
    new_signal: Signal,
    now: datetime | None = None,
) -> Need | None:
    """
    Process a newly ingested signal through the triangulation state machine.
    Returns the Need if corroborated, None if still in watch state.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    window_start = now - timedelta(hours=CORROBORATION_WINDOW_HOURS)

    # Query matching watch-state signals
    stmt = select(Signal).where(
        and_(
            Signal.zone_id == new_signal.zone_id,
            Signal.need_category == new_signal.need_category,
            Signal.state == "watch",
            Signal.collected_at >= window_start,
            Signal.id != new_signal.id,
            Signal.reporter_id != new_signal.reporter_id,  # Different reporter
        )
    )
    result = await db.execute(stmt)
    matching_signals = result.scalars().all()

    if not matching_signals:
        # Stay in watch state
        return None

    # Use the best-matching existing signal for corroboration
    existing_signal = matching_signals[0]

    # Load reporters
    existing_reporter = None
    new_reporter = None
    if existing_signal.reporter_id:
        existing_reporter = await db.get(Reporter, existing_signal.reporter_id)
    if new_signal.reporter_id:
        new_reporter = await db.get(Reporter, new_signal.reporter_id)

    # Compute C score
    c_score = compute_c_score(existing_signal, new_signal, existing_reporter, new_reporter)

    # Determine trust score for decay calculation
    trust_score = 0.65
    if new_reporter:
        trust_score = new_reporter.trust_score

    # Compute T score
    t_score = decay.compute_t_score(
        new_signal.need_category,
        now,
        trust_score=trust_score,
        reference_time=now
    )
    lambda_per_hour = decay.get_effective_lambda(new_signal.need_category, trust_score)

    # Gather all urgencies for scoring
    all_urgencies = [s.urgency for s in matching_signals if s.urgency] + (
        [new_signal.urgency] if new_signal.urgency else []
    )
    signal_count = len(matching_signals) + 1

    # Check if a Need already exists for this zone/category
    existing_need_id = existing_signal.corroboration_id
    if existing_need_id:
        need = await db.get(Need, existing_need_id)
        if need:
            # Update existing need
            need.source_count = signal_count
            need.last_corroborated = now
            need.updated_at = now
            need.c_score = c_score
            need.t_score = t_score
            need.lambda_per_hour = lambda_per_hour

            scores = scoring.compute_all_scores(
                signal_count=signal_count,
                urgencies=all_urgencies,
                need_category=need.need_category,
                c_score=c_score,
                t_score=t_score,
                existing_g=need.g_score,
            )
            need.f_score = scores.f_score
            need.u_score = scores.u_score
            need.priority_score = scores.priority_score

            new_signal.state = "active"
            new_signal.corroboration_id = need.id
            await db.flush()
            return need

    # Create new Need
    pop_est = new_signal.population_est or existing_signal.population_est

    scores = scoring.compute_all_scores(
        signal_count=signal_count,
        urgencies=all_urgencies,
        need_category=new_signal.need_category,
        c_score=c_score,
        t_score=t_score,
    )

    need = Need(
        zone_id=new_signal.zone_id,
        need_category=new_signal.need_category,
        priority_score=scores.priority_score,
        f_score=scores.f_score,
        u_score=scores.u_score,
        g_score=scores.g_score,
        v_score=scores.v_score,
        c_score=c_score,
        t_score=t_score,
        lambda_per_hour=lambda_per_hour,
        source_count=signal_count,
        population_est=pop_est,
        status="active",
        first_reported=existing_signal.collected_at,
        last_corroborated=now,
    )
    db.add(need)
    await db.flush()

    # Link both signals to the need
    existing_signal.state = "active"
    existing_signal.corroboration_id = need.id
    new_signal.state = "active"
    new_signal.corroboration_id = need.id

    return need


async def manually_promote_signal(
    db: AsyncSession,
    signal: Signal,
    coordinator_id: str | None = None,
) -> Need:
    """
    Manual promotion by coordinator — creates/updates Need, logs as override.
    """
    now = datetime.now(timezone.utc)

    trust_score = 0.65
    if signal.reporter_id:
        reporter = await db.get(Reporter, signal.reporter_id)
        if reporter:
            trust_score = reporter.trust_score

    t_score = decay.compute_t_score(signal.need_category, now, trust_score=trust_score, reference_time=now)
    lambda_per_hour = decay.get_effective_lambda(signal.need_category, trust_score)

    scores = scoring.compute_all_scores(
        signal_count=1,
        urgencies=[signal.urgency] if signal.urgency else [3],
        need_category=signal.need_category,
        c_score=0.5,  # default for manual promotion
        t_score=t_score,
    )

    need = Need(
        zone_id=signal.zone_id,
        need_category=signal.need_category,
        priority_score=scores.priority_score,
        f_score=scores.f_score,
        u_score=scores.u_score,
        g_score=scores.g_score,
        v_score=scores.v_score,
        c_score=0.5,
        t_score=t_score,
        lambda_per_hour=lambda_per_hour,
        source_count=1,
        population_est=signal.population_est,
        status="active",
        first_reported=signal.collected_at,
        last_corroborated=now,
    )
    db.add(need)
    await db.flush()

    signal.state = "active"
    signal.corroboration_id = need.id
    return need
