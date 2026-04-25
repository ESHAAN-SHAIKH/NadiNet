"""
Tests for the priority scoring engine — F × U × G × V × C × T formula.
"""
import pytest
from app.services.scoring import (
    compute_f_score, compute_u_score, compute_g_score, compute_v_score,
    compute_priority_score, compute_all_scores,
)


class TestFScore:
    def test_f_clamped_at_1(self):
        assert compute_f_score(10) == 1.0
        assert compute_f_score(100) == 1.0

    def test_f_scales_linearly(self):
        assert compute_f_score(5) == 0.5
        assert compute_f_score(1) == 0.1


class TestUScore:
    def test_u_max_urgency(self):
        assert compute_u_score([5, 5, 5]) == 1.0

    def test_u_mean(self):
        assert compute_u_score([3]) == pytest.approx(0.6)
        assert compute_u_score([2, 4]) == pytest.approx(0.6)

    def test_u_empty_returns_default(self):
        assert compute_u_score([]) == 0.5


class TestGScore:
    def test_g_default(self):
        assert compute_g_score(None) == 0.8

    def test_g_partial_resolution(self):
        g = compute_g_score(0.8, "partial")
        assert g == pytest.approx(0.48)

    def test_g_full_resolution(self):
        g = compute_g_score(0.8, "resolved")
        assert g == pytest.approx(0.05)

    def test_g_no_change_without_resolution(self):
        assert compute_g_score(0.6) == 0.6


class TestVScore:
    def test_v_base(self):
        assert compute_v_score("shelter") == 1.0

    def test_v_medical_bonus(self):
        assert compute_v_score("medical_access") == pytest.approx(1.3)

    def test_v_nutrition_bonus(self):
        assert compute_v_score("nutrition") == pytest.approx(1.3)

    def test_v_elderly_bonus(self):
        v = compute_v_score("shelter", elderly_pct=0.35)
        assert v == pytest.approx(1.2)

    def test_v_children_bonus(self):
        v = compute_v_score("shelter", children_pct=0.25)
        assert v == pytest.approx(1.2)

    def test_v_clamped_at_2(self):
        v = compute_v_score("medical_access", elderly_pct=0.4, children_pct=0.3, extra_vulnerability_count=5)
        assert v == 2.0

    def test_v_clamped_at_1_minimum(self):
        v = compute_v_score("other", 0.0, 0.0, 0)
        assert v == 1.0


class TestPriorityScore:
    def test_all_max_gives_100(self):
        # F=1, U=1, G=1, V=1, C=1, T=1 → score=100
        score = compute_priority_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == 100.0

    def test_score_clamped_to_100(self):
        score = compute_priority_score(2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
        assert score == 100.0

    def test_score_clamped_to_0(self):
        score = compute_priority_score(0.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == 0.0

    def test_resolved_need_falls_below_10(self):
        # G=0.05 for resolved need
        score = compute_priority_score(0.5, 0.8, 0.05, 1.0, 0.7, 1.0)
        assert score < 10.0

    def test_score_rounded_to_1_decimal(self):
        score = compute_priority_score(0.5, 0.6, 0.8, 1.3, 0.72, 0.9)
        assert score == round(score, 1)


class TestComputeAllScores:
    def test_full_score_computation(self):
        scores = compute_all_scores(
            signal_count=5,
            urgencies=[4, 4, 5],
            need_category="medical_access",
            c_score=0.8,
            t_score=0.95,
        )
        assert scores.f_score == pytest.approx(0.5)
        assert scores.v_score == pytest.approx(1.3)
        assert 0 < scores.priority_score <= 100

    def test_g_update_after_debrief(self):
        scores_before = compute_all_scores(5, [4], "nutrition", 0.8, 1.0, existing_g=0.8)
        scores_after = compute_all_scores(5, [4], "nutrition", 0.8, 1.0, existing_g=0.8, resolution="resolved")
        assert scores_after.g_score == pytest.approx(0.05)
        assert scores_after.priority_score < scores_before.priority_score
