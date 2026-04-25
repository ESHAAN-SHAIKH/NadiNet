"""
Trust Decay Engine — implements T(t) = T₀ × e^(−λt)
where λ = ln(2) / half_life_hours, modulated by reporter trust.
"""
import math
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Half-lives in hours by need category
HALF_LIVES: dict[str, float] = {
    "medical_access":   96.0,
    "nutrition":        144.0,
    "elderly_care":     192.0,
    "mental_health":    192.0,
    "water_sanitation": 288.0,
    "shelter":          336.0,
    "education":        336.0,
    "livelihood":       312.0,
    "other":            240.0,
}

T0 = 1.0
REVERIFICATION_THRESHOLD = 0.20
ARCHIVAL_THRESHOLD = 0.05


def get_lambda(need_category: str) -> float:
    """Compute base λ = ln(2) / half_life_hours for a given need category."""
    half_life = HALF_LIVES.get(need_category, HALF_LIVES["other"])
    return math.log(2) / half_life


def get_effective_lambda(need_category: str, trust_score: float) -> float:
    """Apply reporter trust modifier to λ."""
    base_lambda = get_lambda(need_category)
    if trust_score >= 0.85:
        return base_lambda * 0.6   # 40% slower decay
    elif trust_score >= 0.65:
        return base_lambda * 1.0   # base rate
    else:
        return base_lambda * 1.3   # 30% faster decay


def compute_t_score(
    need_category: str,
    last_corroborated: datetime,
    trust_score: float = 0.65,
    reference_time: datetime | None = None
) -> float:
    """
    Compute current T score for a need.
    T(t) = T₀ × e^(−λ_effective × t_hours)
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    # Ensure both are timezone-aware
    if last_corroborated.tzinfo is None:
        last_corroborated = last_corroborated.replace(tzinfo=timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    hours_elapsed = (reference_time - last_corroborated).total_seconds() / 3600.0
    hours_elapsed = max(0.0, hours_elapsed)

    lambda_eff = get_effective_lambda(need_category, trust_score)
    t = T0 * math.exp(-lambda_eff * hours_elapsed)
    return max(0.0, min(1.0, t))


def simulate_t_score(
    current_t: float,
    need_category: str,
    additional_days: float,
    trust_score: float = 0.65
) -> float:
    """
    Simulate T score after additional_days elapsed from now.
    Used by the frontend simulator (values passed in response, computed client-side).
    """
    lambda_eff = get_effective_lambda(need_category, trust_score)
    additional_hours = additional_days * 24.0
    t = current_t * math.exp(-lambda_eff * additional_hours)
    return max(0.0, min(1.0, t))


def should_trigger_reverification(t_score: float) -> bool:
    return t_score < REVERIFICATION_THRESHOLD


def should_archive(t_score: float) -> bool:
    return t_score < ARCHIVAL_THRESHOLD


def update_reporter_decay_modifier(trust_score: float) -> float:
    """Return the decay modifier based on trust score."""
    if trust_score >= 0.85:
        return 0.6
    elif trust_score >= 0.65:
        return 1.0
    else:
        return 1.3
