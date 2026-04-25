"""
Tests for the trust decay engine — T(t) = T₀ × e^(−λt).
"""
import math
import pytest
from datetime import datetime, timezone, timedelta
from app.services.decay import (
    compute_t_score, get_lambda, get_effective_lambda,
    should_trigger_reverification, should_archive,
    simulate_t_score, HALF_LIVES,
)


def hours_ago(h: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)


class TestBasicDecay:
    def test_fresh_report_t_equals_1(self):
        t = compute_t_score("medical_access", hours_ago(0))
        assert t == pytest.approx(1.0, abs=0.01)

    def test_after_one_half_life_t_approx_0_5(self):
        half_life = HALF_LIVES["medical_access"]  # 96 hours
        t = compute_t_score("medical_access", hours_ago(half_life))
        assert t == pytest.approx(0.5, abs=0.01)

    def test_nutrition_half_life(self):
        half_life = HALF_LIVES["nutrition"]  # 144 hours
        t = compute_t_score("nutrition", hours_ago(half_life))
        assert t == pytest.approx(0.5, abs=0.01)

    def test_t_decreases_over_time(self):
        t_early = compute_t_score("shelter", hours_ago(24))
        t_late = compute_t_score("shelter", hours_ago(72))
        assert t_early > t_late

    def test_t_bounded_0_1(self):
        t = compute_t_score("other", hours_ago(10000))
        assert 0.0 <= t <= 1.0


class TestTrustModifiers:
    def test_high_trust_decays_40_percent_slower(self):
        half_life = HALF_LIVES["medical_access"]
        # High trust decays slower → higher T after same time
        t_high = compute_t_score("medical_access", hours_ago(half_life), trust_score=0.90)
        t_base = compute_t_score("medical_access", hours_ago(half_life), trust_score=0.70)
        assert t_high > t_base

        # High trust lambda = base * 0.6, so half-life extends
        lambda_base = get_lambda("medical_access")
        lambda_high = get_effective_lambda("medical_access", 0.90)
        assert lambda_high == pytest.approx(lambda_base * 0.6, rel=0.01)

    def test_low_trust_decays_30_percent_faster(self):
        half_life = HALF_LIVES["medical_access"]
        t_low = compute_t_score("medical_access", hours_ago(half_life), trust_score=0.50)
        t_base = compute_t_score("medical_access", hours_ago(half_life), trust_score=0.70)
        assert t_low < t_base

        lambda_base = get_lambda("medical_access")
        lambda_low = get_effective_lambda("medical_access", 0.50)
        assert lambda_low == pytest.approx(lambda_base * 1.3, rel=0.01)

    def test_medium_trust_uses_base_rate(self):
        lambda_base = get_lambda("nutrition")
        lambda_medium = get_effective_lambda("nutrition", 0.70)
        assert lambda_medium == pytest.approx(lambda_base, rel=0.01)


class TestThresholds:
    def test_t_below_0_20_triggers_reverification(self):
        # Compute how long it takes for T to drop below 0.20
        # T < 0.20 means e^(-λt) < 0.20, t > -ln(0.20)/λ
        lambda_val = get_lambda("medical_access")
        hours_needed = -math.log(0.20) / lambda_val + 1  # +1 to ensure below
        t = compute_t_score("medical_access", hours_ago(hours_needed))
        assert should_trigger_reverification(t)

    def test_t_above_0_20_no_reverification(self):
        t = compute_t_score("medical_access", hours_ago(1))
        assert not should_trigger_reverification(t)

    def test_t_below_0_05_triggers_archive(self):
        lambda_val = get_lambda("education")  # long half-life = 336h
        hours_needed = -math.log(0.05) / lambda_val + 1
        t = compute_t_score("education", hours_ago(hours_needed))
        assert should_archive(t)

    def test_t_above_0_05_no_archive(self):
        t = compute_t_score("shelter", hours_ago(1))
        assert not should_archive(t)


class TestSimulation:
    def test_simulate_always_lower_than_current(self):
        current_t = 0.8
        simulated = simulate_t_score(current_t, "nutrition", additional_days=7)
        assert simulated < current_t

    def test_simulate_zero_days_unchanged(self):
        current_t = 0.75
        simulated = simulate_t_score(current_t, "shelter", additional_days=0)
        assert simulated == pytest.approx(current_t, abs=0.001)
