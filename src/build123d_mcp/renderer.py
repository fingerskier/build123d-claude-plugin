"""Headless rendering of build123d shapes to SVG and PNG images."""

import base64
import io
import math
from typing import Any

# Standard view directions as (eye_x, eye_y, eye_z) vectors
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


def render_svg(
    shape: Any,
    view: str = "iso",
    width: int = 800,
    height: int = 600,
) -> str:
    """Render a build123d shape to SVG string.

    Args:
        shape: A build123d shape object.
        view: View angle name (iso, front, back, right, left, top, bottom).
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        SVG content as a string.
    """
    from build123d import export_svg, Axis, Vector

    view_dir = VIEW_ANGLES.get(view, VIEW_ANGLES["iso"])
    view_dir = _normalize(view_dir)

    # build123d's export_svg expects a viewport_origin (the eye direction)
    try:
        svg_content = export_svg(
            shape,
            viewport_origin=Vector(view_dir[0] * 100, view_dir[1] * 100, view_dir[2] * 100),
        )
    except TypeError:
        # Fallback if export_svg API differs
        svg_content = export_svg(shape)

    return svg_content


def render_png(
    shape: Any,
    view: str = "iso",
    width: int = 800,
    height: int = 600,
) -> bytes:
    """Render a build123d shape to PNG bytes.

    Uses SVG intermediate representation and CairoSVG for rasterization.

    Args:
        shape: A build123d shape object.
        view: View angle name.
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
        # Fallback: use Pillow to create a simple placeholder
        from PIL import Image, ImageDraw, ImageFont

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
        view: View angle name.
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
    from pathlib import Path

    svg_content = render_svg(shape, view=view, **kwargs)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg_content, encoding="utf-8")
    return str(path)


def save_png(shape: Any, file_path: str, view: str = "iso", **kwargs: Any) -> str:
    """Render and save a PNG file.

    Returns:
        The file path written.
    """
    from pathlib import Path

    png_bytes = render_png(shape, view=view, **kwargs)
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes)
    return str(path)
