"""Testes do mapeamento puro decay→health e phase→evento."""

import pytest

from aquario.lifecycle import (
    FREAKING_OUT_S,
    event_for_phase,
    health_from_elapsed,
)


# ─── health_from_elapsed ─────────────────────────────────────────────────

class TestHealthFromElapsed:
    def test_zero_is_full_health(self):
        assert health_from_elapsed(0) == pytest.approx(1.0)

    def test_negative_clamps_to_full(self):
        # Spawn racing com tempo monotônico — não negativa.
        assert health_from_elapsed(-1) == pytest.approx(1.0)

    def test_15min_around_freaking_out_threshold(self):
        # Ponto-âncora do brief: 15min ≈ 0.4.
        assert health_from_elapsed(900) == pytest.approx(0.40)

    def test_30min_minimum_health(self):
        # Ponto-âncora do brief: 30min ≈ 0.05.
        assert health_from_elapsed(1800) == pytest.approx(0.05)

    def test_far_future_stays_at_minimum(self):
        # Após 30min mantém 0.05 — Meeseeks não vai pra zero por decay,
        # só por evento terminal explícito.
        assert health_from_elapsed(3600) == pytest.approx(0.05)

    def test_3min_corner_matches_curve(self):
        assert health_from_elapsed(180) == pytest.approx(0.85)

    def test_8min_corner_matches_curve(self):
        assert health_from_elapsed(480) == pytest.approx(0.65)

    def test_25min_corner_matches_curve(self):
        assert health_from_elapsed(1500) == pytest.approx(0.15)

    def test_monotonically_decreasing(self):
        prev = 2.0
        for t in range(0, 2000, 30):
            h = health_from_elapsed(t)
            assert h <= prev
            prev = h

    def test_health_in_unit_range(self):
        for t in (0, 60, 300, 600, 900, 1200, 1800, 5000):
            h = health_from_elapsed(t)
            assert 0.0 <= h <= 1.0


def test_freaking_out_constant_matches_15min():
    assert FREAKING_OUT_S == 900


# ─── event_for_phase ─────────────────────────────────────────────────────

class TestEventForPhase:
    def test_success_dies_happy(self):
        assert event_for_phase("success") == "died_happy"

    def test_meeseeks_failure_dies_defeated(self):
        assert event_for_phase("meeseeks_failure") == "died_defeated"

    def test_dev_server_failure_dies_defeated(self):
        # Meeseeks completou a missão de código, mas o pipeline falhou
        # depois — pro aquário ainda conta como morte derrotada.
        assert event_for_phase("dev_server_failure") == "died_defeated"

    def test_garagem_pushback_is_silent(self):
        # Meeseeks nem nasceu nesse caminho — não emite morte.
        assert event_for_phase("garagem_pushback") is None

    def test_garagem_error_is_silent(self):
        assert event_for_phase("garagem_error") is None

    def test_garagem_no_slug_is_silent(self):
        assert event_for_phase("garagem_no_slug") is None

    def test_unknown_phase_is_silent(self):
        assert event_for_phase("aliens_invaded") is None
