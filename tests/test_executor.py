"""Tests for the build123d code executor."""

import pytest
from build123d_mcp.executor import execute_code, SecurityError, ExecutionError, _validate_ast


class TestASTValidation:
    def test_allowed_imports(self):
        _validate_ast("import math")
        _validate_ast("from build123d import Box")
        _validate_ast("import build123d")

    def test_blocked_imports(self):
        with pytest.raises(SecurityError, match="not allowed"):
            _validate_ast("import os")

        with pytest.raises(SecurityError, match="not allowed"):
            _validate_ast("import subprocess")

        with pytest.raises(SecurityError, match="not allowed"):
            _validate_ast("from pathlib import Path")

        with pytest.raises(SecurityError, match="not allowed"):
            _validate_ast("import sys")

    def test_blocked_dunder_access(self):
        with pytest.raises(SecurityError, match="dunder"):
            _validate_ast("x.__subclasses__()")

    def test_syntax_error(self):
        with pytest.raises(ExecutionError, match="Syntax error"):
            _validate_ast("def foo(")


class TestExecution:
    def test_simple_box(self):
        result = execute_code(
            "result = Box(10, 20, 30)",
            timeout=30,
        )
        assert result.success
        assert result.shape is not None

    def test_builder_mode(self):
        code = """
with BuildPart() as part:
    Box(10, 10, 10)
result = part.part
"""
        result = execute_code(code, timeout=30)
        assert result.success
        assert result.shape is not None

    def test_auto_detect_builder(self):
        code = """
with BuildPart() as part:
    Box(5, 5, 5)
"""
        result = execute_code(code, timeout=30)
        assert result.success

    def test_algebra_mode(self):
        code = """
box = Box(10, 10, 10)
cyl = Cylinder(3, 20)
result = box - cyl
"""
        result = execute_code(code, timeout=30)
        assert result.success

    def test_security_blocks_os(self):
        with pytest.raises(SecurityError):
            execute_code("import os; os.system('echo pwned')")

    def test_no_shape_error(self):
        result = execute_code("x = 42", timeout=10)
        assert not result.success
        assert "No shape found" in result.error

    def test_runtime_error(self):
        result = execute_code("result = Box(0, 0, 0)", timeout=10)
        # May succeed or fail depending on build123d validation
        # Just ensure it doesn't crash the executor
        assert isinstance(result.error, (str, type(None)))

    def test_print_output_captured(self):
        code = """
print("hello from build123d")
result = Box(10, 10, 10)
"""
        result = execute_code(code, timeout=30)
        assert result.success
        assert "hello" in result.output
