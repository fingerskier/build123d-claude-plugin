"""Sandboxed build123d code execution engine."""

import ast
import logging
import signal
import traceback
from typing import Any

logger = logging.getLogger(__name__)

# Modules allowed in executed code
ALLOWED_MODULES = frozenset({
    "math",
    "typing",
    "build123d",
    "collections",
    "itertools",
    "functools",
    "dataclasses",
    "enum",
})

# Builtins blocked from executed code
BLOCKED_BUILTINS = frozenset({
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "exit",
    "quit",
    "breakpoint",
    "input",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "memoryview",
})

EXECUTION_TIMEOUT = 60  # seconds


class ExecutionError(Exception):
    """Raised when code execution fails."""


class SecurityError(ExecutionError):
    """Raised when code violates security constraints."""


def _validate_ast(code: str) -> None:
    """Scan AST for disallowed patterns before execution."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.debug("Syntax error in submitted code: %s", e)
        raise ExecutionError(f"Syntax error: {e}") from e

    for node in ast.walk(tree):
        # Check import statements
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module not in ALLOWED_MODULES:
                    logger.warning("Blocked import attempt: %s", alias.name)
                    raise SecurityError(
                        f"Import of '{alias.name}' is not allowed. "
                        f"Allowed modules: {', '.join(sorted(ALLOWED_MODULES))}"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module not in ALLOWED_MODULES:
                    logger.warning("Blocked import attempt: from %s", node.module)
                    raise SecurityError(
                        f"Import from '{node.module}' is not allowed. "
                        f"Allowed modules: {', '.join(sorted(ALLOWED_MODULES))}"
                    )
        # Block access to dunder attributes (except __init__, __name__, __class__)
        elif isinstance(node, ast.Attribute):
            if (
                node.attr.startswith("__")
                and node.attr.endswith("__")
                and node.attr not in ("__init__", "__name__", "__class__", "__doc__")
            ):
                logger.warning("Blocked dunder access: %s", node.attr)
                raise SecurityError(
                    f"Access to dunder attribute '{node.attr}' is not allowed."
                )


def _make_safe_builtins() -> dict[str, Any]:
    """Create a restricted builtins dict."""
    import builtins

    safe = {}
    for name in dir(builtins):
        if name not in BLOCKED_BUILTINS and not name.startswith("_"):
            safe[name] = getattr(builtins, name)
    return safe


def _make_namespace() -> dict[str, Any]:
    """Create the execution namespace pre-populated with build123d imports."""
    import build123d

    namespace: dict[str, Any] = {"__builtins__": _make_safe_builtins()}

    # Import all public build123d names into namespace
    for name in dir(build123d):
        if not name.startswith("_"):
            namespace[name] = getattr(build123d, name)

    # Also make the module available for `from build123d import ...` style
    namespace["build123d"] = build123d

    # Add math module
    import math

    namespace["math"] = math
    for name in dir(math):
        if not name.startswith("_"):
            namespace[name] = getattr(math, name)

    return namespace


def _timeout_handler(signum: int, frame: Any) -> None:
    raise ExecutionError(
        f"Code execution timed out after {EXECUTION_TIMEOUT} seconds."
    )


def _execute_in_process(code: str, timeout: int) -> ExecutionResult:
    """Execute code in a subprocess with a hard timeout.

    Used when signal-based timeout is unavailable (non-main thread).
    Runs the code in a forked process via concurrent.futures so that
    C-level blocking calls can be reliably interrupted.
    """
    import concurrent.futures

    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_sandboxed, code)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("Code execution timed out after %ds (process-based)", timeout)
            raise ExecutionError(
                f"Code execution timed out after {timeout} seconds."
            )


def _run_sandboxed(code: str) -> ExecutionResult:
    """Entry point for subprocess execution — runs pre-validated code."""
    import io
    import sys

    namespace = _make_namespace()
    stdout_capture = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = stdout_capture
        exec(code, namespace)  # noqa: S102
        shape = _find_result(namespace, code)
        output = stdout_capture.getvalue()
        if shape is None:
            return ExecutionResult(
                shape=None,
                output=output,
                namespace={},
                error="No shape found in code output. "
                "Assign a build123d shape to 'result' or use a BuildPart context manager.",
            )
        return ExecutionResult(shape=shape, output=output, namespace={})
    except Exception as e:
        logger.error("Execution error in sandboxed code: %s: %s", type(e).__name__, e)
        tb = traceback.format_exc()
        return ExecutionResult(
            shape=None,
            output=stdout_capture.getvalue(),
            namespace={},
            error=f"{type(e).__name__}: {e}\n\n{tb}",
        )
    finally:
        sys.stdout = old_stdout


def _find_result(namespace: dict[str, Any], code: str) -> Any:
    """Find the resulting shape from executed code.

    Looks for:
    1. A variable named 'result'
    2. The last assigned variable that is a build123d shape
    3. Any BuildPart/BuildSketch/BuildLine context manager result
    """
    import build123d

    shape_types = (
        build123d.Part,
        build123d.Sketch,
        build123d.Curve,
        build123d.Compound,
        build123d.Solid,
        build123d.Shell,
        build123d.Face,
        build123d.Wire,
        build123d.Edge,
    )

    # 1. Check for explicit 'result' variable
    if "result" in namespace and isinstance(namespace["result"], shape_types):
        return namespace["result"]

    # 2. Check for builder context manager results
    builder_types = (
        build123d.BuildPart,
        build123d.BuildSketch,
        build123d.BuildLine,
    )
    builders = []
    for name, val in namespace.items():
        if name.startswith("_"):
            continue
        if isinstance(val, builder_types):
            builders.append(val)

    if builders:
        # Return the last builder's result
        builder = builders[-1]
        if hasattr(builder, "part") and builder.part is not None:
            return builder.part
        if hasattr(builder, "sketch") and builder.sketch is not None:
            return builder.sketch
        if hasattr(builder, "line") and builder.line is not None:
            return builder.line

    # 3. Find last assigned shape by parsing AST for assignment targets
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    # Collect assignment target names in source order (top-level statements only)
    assigned_names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned_names.append(node.target.id)

    # Check assigned names in reverse order for shape objects
    for name in reversed(assigned_names):
        if name in namespace and isinstance(namespace[name], shape_types):
            return namespace[name]

    # 4. Check any variable that's a shape
    for name, val in namespace.items():
        if name.startswith("_") or name == "__builtins__":
            continue
        if isinstance(val, shape_types):
            return val

    return None


class ExecutionResult:
    """Result of executing build123d code."""

    def __init__(
        self,
        shape: Any | None,
        output: str,
        namespace: dict[str, Any],
        error: str | None = None,
    ):
        self.shape = shape
        self.output = output
        self.namespace = namespace
        self.error = error

    @property
    def success(self) -> bool:
        return self.error is None and self.shape is not None


def execute_code(code: str, timeout: int = EXECUTION_TIMEOUT) -> ExecutionResult:
    """Execute build123d code in a sandboxed namespace.

    Args:
        code: Python code string using build123d API.
        timeout: Maximum execution time in seconds.

    Returns:
        ExecutionResult with the shape, output, and any errors.
    """
    logger.debug("Executing code (%d chars, timeout=%ds)", len(code), timeout)

    # Validate AST for security
    _validate_ast(code)

    # Build namespace
    namespace = _make_namespace()

    # Capture stdout
    import io
    import sys

    stdout_capture = io.StringIO()

    # Use signal-based timeout on main thread, process-based otherwise
    import threading

    use_signal = threading.current_thread() is threading.main_thread()
    logger.debug("Main thread: %s, using %s timeout", use_signal, "signal" if use_signal else "process")

    if use_signal:
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout)
        except (OSError, AttributeError):
            use_signal = False

    if not use_signal:
        # Delegate to a subprocess for reliable timeout
        return _execute_in_process(code, timeout)

    old_stdout = sys.stdout
    try:
        sys.stdout = stdout_capture
        exec(code, namespace)  # noqa: S102

        shape = _find_result(namespace, code)
        output = stdout_capture.getvalue()

        if shape is None:
            logger.info("Code executed but no shape found in result")
            return ExecutionResult(
                shape=None,
                output=output,
                namespace=namespace,
                error="No shape found in code output. "
                "Assign a build123d shape to 'result' or use a BuildPart context manager.",
            )

        logger.info("Code executed successfully, shape found")
        return ExecutionResult(shape=shape, output=output, namespace=namespace)

    except ExecutionError:
        raise
    except Exception as e:
        logger.error("Execution error: %s: %s", type(e).__name__, e)
        tb = traceback.format_exc()
        return ExecutionResult(
            shape=None,
            output=stdout_capture.getvalue(),
            namespace=namespace,
            error=f"{type(e).__name__}: {e}\n\n{tb}",
        )
    finally:
        sys.stdout = old_stdout
        try:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        except (OSError, AttributeError, UnboundLocalError):
            pass
