"""Tests for the build123d code executor."""

import pytest
from build123d_mcp.executor import (
    execute_code,
    SecurityError,
    ExecutionError,
    _validate_ast,
    _make_safe_builtins,
)


class TestASTValidation:
    """Pure-logic tests that don't need build123d installed."""
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

    def test_security_blocks_os_via_execute(self):
        """execute_code raises SecurityError before needing build123d."""
        with pytest.raises(SecurityError):
            execute_code("import os; os.system('echo pwned')")


class TestSandboxBuiltins:
    """The restricted builtins must still support normal language features.

    These run without build123d installed because they exec plain Python in a
    namespace built from _make_safe_builtins().
    """

    def _ns(self):
        return {"__builtins__": _make_safe_builtins(), "__name__": "build123d_sandbox"}

    def test_allowed_import_executes(self):
        ns = self._ns()
        exec("import math\nresult = math.sqrt(16)", ns)
        assert ns["result"] == 4

    def test_allowed_from_import_executes(self):
        ns = self._ns()
        exec("from itertools import count\nresult = next(count(5))", ns)
        assert ns["result"] == 5

    def test_blocked_import_raises_at_runtime(self):
        with pytest.raises(ImportError, match="not allowed"):
            exec("import os", self._ns())

    def test_relative_import_blocked(self):
        with pytest.raises(ImportError):
            exec("__import__('x', level=1)", self._ns())

    def test_class_definition_supported(self):
        ns = self._ns()
        exec("class P:\n    def __init__(self): self.v = 7\nresult = P().v", ns)
        assert ns["result"] == 7

    def test_dataclass_supported(self):
        ns = self._ns()
        exec(
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Pt:\n"
            "    x: int\n"
            "result = Pt(3).x",
            ns,
        )
        assert ns["result"] == 3

    def test_dangerous_builtins_removed(self):
        for name in ("open", "exec", "eval", "compile", "getattr"):
            with pytest.raises(NameError):
                exec(name, self._ns())


_has_build123d = pytest.importorskip is not None  # just a namespace anchor
try:
    import build123d as _b123d  # noqa: F401
    _has_build123d = True
except ImportError:
    _has_build123d = False


@pytest.mark.skipif(not _has_build123d, reason="build123d not installed")
class TestExecution:
    """Integration tests that require build123d."""

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
