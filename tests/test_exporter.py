"""Tests for the build123d exporter."""

import json
import tempfile
from pathlib import Path

import pytest
from build123d import Box

from build123d_mcp.exporter import export_stl, export_step, get_model_properties, properties_summary


@pytest.fixture
def sample_box():
    return Box(10, 20, 30)


class TestModelProperties:
    def test_bounding_box(self, sample_box):
        props = get_model_properties(sample_box)
        assert props["bounding_box"] is not None
        size = props["bounding_box"]["size"]
        assert abs(size["x"] - 10) < 0.01
        assert abs(size["y"] - 20) < 0.01
        assert abs(size["z"] - 30) < 0.01

    def test_volume(self, sample_box):
        props = get_model_properties(sample_box)
        assert props["volume"] is not None
        assert abs(props["volume"] - 6000) < 1  # 10 * 20 * 30

    def test_topology_counts(self, sample_box):
        props = get_model_properties(sample_box)
        assert props["face_count"] == 6
        assert props["edge_count"] == 12
        assert props["vertex_count"] == 8

    def test_properties_summary(self, sample_box):
        summary = properties_summary(sample_box)
        assert "10.0 x 20.0 x 30.0" in summary
        assert "6000" in summary
        assert "6 faces" in summary


class TestExportSTL:
    def test_export_stl(self, sample_box):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.stl"
            result = export_stl(sample_box, path)
            assert result.exists()
            assert result.stat().st_size > 0

    def test_export_stl_creates_dirs(self, sample_box):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "deep" / "test.stl"
            result = export_stl(sample_box, path)
            assert result.exists()


class TestExportSTEP:
    def test_export_step(self, sample_box):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.step"
            result = export_step(sample_box, path)
            assert result.exists()
            assert result.stat().st_size > 0
