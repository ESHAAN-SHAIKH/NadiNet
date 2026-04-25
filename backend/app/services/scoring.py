"""
Priority Scoring Engine — Score = F × U × G × V × C × T × 100
All component scores pre-computed and stored; never computed on read.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

HIGH_VULNERABILITY_CATEGORIES = {"medical_access", "nutrition"}


@dataclass
class ScoreComponents:
    f_score: float
    u_score: float
    g_score: float
    v_score: float
    c_score: float
    t_score: float
    priority_score: float


def compute_f_score(signal_count: int) -> float:
    """F = min(signal_count / 10, 1.0)"""
    return min(signal_count / 10.0, 1.0)


def compute_u_score(urgencies: list[int]) -> float:
    """U = mean(urgency) / 5"""
    if not urgencies:
        return 0.5
    return sum(urgencies) / len(urgencies) / 5.0


def compute_g_score(
    existing_g: float | None,
    resolution: str | None = None
) -> float:
    """
    G = coverage gap between 0.0 (fully covered) and 1.0 (no service).
    Default 0.8 until a debrief updates it.
    """
    if existing_g is None:
        return 0.8

    if resolution == "partial":
        return existing_g * 0.6
    elif resolution == "resolved":
        return 0.05
    return existing_g


def compute_v_score(
    need_category: str,
    elderly_pct: float = 0.0,
    children_pct: float = 0.0,
    extra_vulnerability_count: int = 0
) -> float:
    """
    V base = 1.0
    +0.3 if medical_access or nutrition
    +0.2 if elderly > 30%
    +0.2 if children < 5y > 20%
    +0.1 per extra vulnerability indicator
    Clamped to [1.0, 2.0]
    """
    v = 1.0
    if need_category in HIGH_VULNERABILITY_CATEGORIES:
        v += 0.3
    if elderly_pct > 0.30:
        v += 0.2
    if children_pct > 0.20:
        v += 0.2
    v += extra_vulnerability_count * 0.1
    return max(1.0, min(2.0, v))


def compute_priority_score(
    f: float,
    u: float,
    g: float,
    v: float,
    c: float,
    t: float
) -> float:
    """
    Final: Score = F × U × G × V × C × T × 100, clamped to [0, 100].
    """
    raw = f * u * g * v * c * t * 100.0
    return round(max(0.0, min(100.0, raw)), 1)


def compute_all_scores(
    signal_count: int,
    urgencies: list[int],
    need_category: str,
    c_score: float,
    t_score: float,
    existing_g: float | None = None,
    resolution: str | None = None,
    elderly_pct: float = 0.0,
    children_pct: float = 0.0,
    extra_vulnerability_count: int = 0,
) -> ScoreComponents:
    """Compute all score components and final priority score."""
    f = compute_f_score(signal_count)
    u = compute_u_score(urgencies)
    g = compute_g_score(existing_g, resolution)
    v = compute_v_score(need_category, elderly_pct, children_pct, extra_vulnerability_count)
    priority = compute_priority_score(f, u, g, v, c_score, t_score)

    return ScoreComponents(
        f_score=round(f, 4),
        u_score=round(u, 4),
        g_score=round(g, 4),
        v_score=round(v, 4),
        c_score=round(c_score, 4),
        t_score=round(t_score, 4),
        priority_score=priority,
    )
