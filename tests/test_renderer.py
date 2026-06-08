"""Tests for the build123d renderer."""

import pytest

from build123d_mcp.renderer import (
    VIEW_ANGLES,
    _normalize,
    _up_vector,
    render_svg,
)


class TestPureLogic:
    """Tests that don't need build123d installed."""

    def test_normalize_unit_length(self):
        x, y, z = _normalize((3, 0, 4))
        assert abs((x ** 2 + y ** 2 + z ** 2) ** 0.5 - 1.0) < 1e-9

    def test_normalize_zero_vector(self):
        assert _normalize((0, 0, 0)) == (0.0, 0.0, 1.0)

    def test_up_vector_default_is_z(self):
        assert _up_vector(_normalize(VIEW_ANGLES["iso"])) == (0.0, 0.0, 1.0)
        assert _up_vector(_normalize(VIEW_ANGLES["front"])) == (0.0, 0.0, 1.0)

    def test_up_vector_for_top_and_bottom_avoids_collinear(self):
        # Top/bottom look along ±Z, so the up vector must not also be ±Z.
        assert _up_vector(_normalize(VIEW_ANGLES["top"])) == (0.0, 1.0, 0.0)
        assert _up_vector(_normalize(VIEW_ANGLES["bottom"])) == (0.0, 1.0, 0.0)

    def test_all_documented_views_present(self):
        assert set(VIEW_ANGLES) == {
            "iso", "front", "back", "right", "left", "top", "bottom", "iso_back",
        }

    def test_render_svg_rejects_unknown_view_before_importing_build123d(self):
        # View validation happens before the build123d import, so this raises
        # ValueError even when build123d isn't installed.
        with pytest.raises(ValueError, match="Unknown view"):
            render_svg(object(), view="diagonal")


_has_build123d = True
try:
    import build123d as _b123d  # noqa: F401
except ImportError:
    _has_build123d = False


@pytest.mark.skipif(not _has_build123d, reason="build123d not installed")
class TestRenderWithBuild123d:
    """Integration tests that require build123d."""

    @pytest.fixture
    def box(self):
        from build123d import Box

        return Box(10, 20, 30)

    def test_render_svg_returns_svg_string(self, box):
        svg = render_svg(box, view="iso", width=400, height=300)
        assert isinstance(svg, str)
        assert "<svg" in svg.lower()

    @pytest.mark.parametrize("view", sorted(VIEW_ANGLES))
    def test_render_svg_all_views(self, box, view):
        svg = render_svg(box, view=view, width=200, height=200)
        assert "<svg" in svg.lower()
