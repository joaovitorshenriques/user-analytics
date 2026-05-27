"""
tests/test_metrics.py
---------------------
Testes unitários para analytics.metrics.compute_metrics.

Cobre: filtro de caracteres, cálculo de médias, limiar de status ativo,
edge cases (lista vazia, filtro que zera resultados).
"""

from __future__ import annotations

import pytest

from analytics.metrics import compute_metrics, UserMetrics


# =============================================================================
# Fixtures
# =============================================================================

def _make_post(post_id: int, body: str, comment_count: int) -> dict:
    return {
        "id":    post_id,
        "title": f"Post {post_id}",
        "body":  body,
        "_comment_count": comment_count,
    }


@pytest.fixture
def sample_posts():
    return [
        _make_post(1, "a" * 100, 3),
        _make_post(2, "b" * 50,  5),
        _make_post(3, "c" * 10,  1),
    ]


# =============================================================================
# Testes de filtragem
# =============================================================================

class TestFiltering:

    def test_no_filter_keeps_all_posts(self, sample_posts):
        m = compute_metrics(sample_posts, min_chars=0, min_posts=1)
        assert m.total_posts == 3
        assert m.raw_total   == 3

    def test_min_chars_filters_correctly(self, sample_posts):
        m = compute_metrics(sample_posts, min_chars=51, min_posts=1)
        assert m.total_posts == 1
        assert m.filtered_posts[0]["id"] == 1

    def test_min_chars_exact_boundary(self, sample_posts):
        # post com exatamente 50 chars deve passar quando min_chars=50
        m = compute_metrics(sample_posts, min_chars=50, min_posts=1)
        assert m.total_posts == 2

    def test_filter_zeros_all_posts(self, sample_posts):
        m = compute_metrics(sample_posts, min_chars=9999, min_posts=1)
        assert m.total_posts  == 0
        assert m.avg_chars    == 0.0
        assert m.avg_comments == 0.0

    def test_empty_post_list(self):
        m = compute_metrics([], min_chars=0, min_posts=5)
        assert m.raw_total   == 0
        assert m.total_posts == 0
        assert m.is_active   is False


# =============================================================================
# Testes de cálculo de médias
# =============================================================================

class TestAverages:

    def test_avg_chars_single_post(self):
        posts = [_make_post(1, "x" * 80, 4)]
        m = compute_metrics(posts, min_chars=0)
        assert m.avg_chars == 80.0

    def test_avg_chars_multiple_posts(self, sample_posts):
        m = compute_metrics(sample_posts, min_chars=0)
        expected = round((100 + 50 + 10) / 3, 2)
        assert m.avg_chars == expected

    def test_avg_comments_single_post(self):
        posts = [_make_post(1, "hello", 7)]
        m = compute_metrics(posts)
        assert m.avg_comments == 7.0

    def test_avg_comments_multiple_posts(self, sample_posts):
        m = compute_metrics(sample_posts, min_chars=0)
        expected = round((3 + 5 + 1) / 3, 2)
        assert m.avg_comments == expected

    def test_avg_comments_after_filter(self, sample_posts):
        # Após filtro só sobra post 1 (100 chars, 3 comentários)
        m = compute_metrics(sample_posts, min_chars=51)
        assert m.avg_comments == 3.0


# =============================================================================
# Testes de status ativo/inativo
# =============================================================================

class TestActiveStatus:

    def test_active_when_raw_total_meets_threshold(self, sample_posts):
        # 3 posts no total, limiar = 3 → ativo
        m = compute_metrics(sample_posts, min_posts=3)
        assert m.is_active is True
        assert m.status    == "Ativo"

    def test_inactive_when_raw_total_below_threshold(self, sample_posts):
        # 3 posts no total, limiar = 4 → inativo
        m = compute_metrics(sample_posts, min_posts=4)
        assert m.is_active is False
        assert m.status    == "Inativo"

    def test_status_based_on_raw_total_not_filtered(self, sample_posts):
        """Status usa o total real de posts, não o filtrado."""
        # Filtra para 1 post, mas total real é 3 — limiar = 3 → ativo
        m = compute_metrics(sample_posts, min_chars=51, min_posts=3)
        assert m.total_posts == 1   # filtrado
        assert m.raw_total   == 3   # real
        assert m.is_active   is True


# =============================================================================
# Testes do dataclass UserMetrics
# =============================================================================

class TestUserMetrics:

    def test_result_is_frozen(self, sample_posts):
        m = compute_metrics(sample_posts)
        with pytest.raises((AttributeError, TypeError)):
            m.total_posts = 99  # type: ignore

    def test_thresholds_preserved_in_result(self, sample_posts):
        m = compute_metrics(sample_posts, min_chars=25, min_posts=7)
        assert m.min_chars_threshold == 25
        assert m.min_posts_threshold == 7
