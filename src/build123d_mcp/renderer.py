"""Headless rendering of build123d shapes to SVG and PNG images.

A 3D shape is projected to 2D edges with hidden-line removal via
``Shape.project_to_viewport`` and written to SVG with the ``ExportSVG`` class
(build123d has no top-level ``export_svg`` function). PNGs are produced by
rasterizing that SVG with CairoSVG.
"""

import base64
import io
import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Standard view directions as (eye_x, eye_y, eye_z) vectors (camera direction
# from the model centre toward the camera).
VIEW_ANGLES: dict[str, tuple[float, float, float]] = {
    "iso": (1, -1, 0.7),         # Isometric
    "front": (0, -1, 0),         # Front (XZ plane)
    "back": (0, 1, 0),           # Back
    "right": (1, 0, 0),          # Right (YZ plane)
    "left": (-1, 0, 0),          # Left
    "top": (0, 0, 1),            # Top (XY plane)
    "bottom": (0, 0, -1),        # Bottom
    "iso_back": (-1, 1, 0.7),    # Isometric from back
}


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    mag = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if mag == 0:
        return (0.0, 0.0, 1.0)
    return (v[0] / mag, v[1] / mag, v[2] / mag)


def _up_vector(direction: tuple[float, float, float]) -> tuple[float, float, float]:
    """Pick a camera "up" vector that is not collinear with the view direction.

    The world up axis is +Z, but for top/bottom views the view direction is
    parallel to +Z, which would make the camera orientation degenerate. In that
    case fall back to +Y.
    """
    if abs(direction[0]) < 1e-6 and abs(direction[1]) < 1e-6:
        return (0.0, 1.0, 0.0)
    return (0.0, 0.0, 1.0)


def render_svg(
    shape: Any,
    view: str = "iso",
    width: int = 800,
    height: int = 600,
) -> str:
    """Render a build123d shape to an SVG string.

    Args:
        shape: A build123d shape object.
        view: View name (iso, front, back, right, left, top, bottom, iso_back).
        width: Target image width in pixels.
        height: Target image height in pixels.

    Returns:
        SVG content as a string.
    """
    if view not in VIEW_ANGLES:
        raise ValueError(
            f"Unknown view '{view}'. Available views: {', '.join(VIEW_ANGLES)}"
        )

    from build123d import Compound, ExportSVG, LineType, Vector

    direction = _normalize(VIEW_ANGLES[view])
    up = _up_vector(direction)

    # Place the camera relative to the model so the whole part stays in frame.
    try:
        bbox = shape.bounding_box()
        center = bbox.center()
        model_size = max(bbox.size.X, bbox.size.Y, bbox.size.Z, 1.0)
    except Exception:
        logger.debug("Could not compute bounding box; using defaults")
        center = Vector(0, 0, 0)
        model_size = 100.0

    distance = model_size * 3
    origin = Vector(
        center.X + direction[0] * distance,
        center.Y + direction[1] * distance,
        center.Z + direction[2] * distance,
    )

    visible, hidden = shape.project_to_viewport(
        viewport_origin=origin,
        viewport_up=Vector(*up),
        look_at=center,
    )

    # Scale the drawing so its largest dimension fills the requested canvas.
    scale = 1.0
    try:
        proj = Compound(children=list(visible) + list(hidden))
        proj_size = max(proj.bounding_box().size.X, proj.bounding_box().size.Y, 1.0)
        scale = max(width, height) / proj_size
    except Exception:
        logger.debug("Could not size projection; using scale=1.0")

    exporter = ExportSVG(scale=scale)
    exporter.add_layer("Visible")
    exporter.add_shape(visible, layer="Visible")
    if hidden:
        exporter.add_layer("Hidden", line_color=(128, 128, 128), line_type=LineType.ISO_DOT)
        exporter.add_shape(hidden, layer="Hidden")

    # ExportSVG writes to a file path; round-trip through a temp file to get a
    # string back.
    fd, tmp_path = tempfile.mkstemp(suffix=".svg")
    os.close(fd)
    try:
        exporter.write(tmp_path)
        return Path(tmp_path).read_text(encoding="utf-8")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def render_png(
    shape: Any,
    view: str = "iso",
    width: int = 800,
    height: int = 600,
) -> bytes:
    """Render a build123d shape to PNG bytes.

    Uses an SVG intermediate representation and CairoSVG for rasterization.

    Args:
        shape: A build123d shape object.
        view: View name.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        PNG image as bytes.
    """
    svg_content = render_svg(shape, view=view, width=width, height=height)

    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(
            bytestring=svg_content.encode("utf-8") if isinstance(svg_content, str) else svg_content,
            output_width=width,
            output_height=height,
        )
        return png_bytes
    except ImportError:
        logger.warning("CairoSVG not available, using Pillow placeholder")
        # Fallback: use Pillow to create a simple placeholder
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)
        draw.text(
            (20, height // 2 - 10),
            "Install CairoSVG for PNG rendering: pip install CairoSVG",
            fill="black",
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def render_png_base64(
    shape: Any,
    view: str = "iso",
    width: int = 800,
    height: int = 600,
) -> str:
    """Render a build123d shape to a base64-encoded PNG string.

    Args:
        shape: A build123d shape object.
        view: View name.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        Base64-encoded PNG string.
    """
    png_bytes = render_png(shape, view=view, width=width, height=height)
    return base64.b64encode(png_bytes).decode("ascii")


def save_svg(shape: Any, file_path: str, view: str = "iso", **kwargs: Any) -> str:
    """Render and save an SVG file.

    Returns:
        The file path written.
    """
    svg_content = render_svg(shape, view=view, **kwargs)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg_content, encoding="utf-8")
    logger.debug("Saved SVG to %s", path)
    return str(path)


def save_png(shape: Any, file_path: str, view: str = "iso", **kwargs: Any) -> str:
    """Render and save a PNG file.

    Returns:
        The file path written.
    """
    png_bytes = render_png(shape, view=view, **kwargs)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes)
    logger.debug("Saved PNG to %s", path)
    return str(path)
