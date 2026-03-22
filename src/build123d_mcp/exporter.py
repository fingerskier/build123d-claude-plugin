"""Export build123d shapes to STL, STEP, and extract model properties."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def get_model_properties(shape: Any) -> dict[str, Any]:
    """Extract geometric properties from a build123d shape.

    Returns a dict with bounding box, volume, surface area, and topology counts.
    """
    props: dict[str, Any] = {}

    try:
        bb = shape.bounding_box()
        props["bounding_box"] = {
            "min": {"x": round(bb.min.X, 4), "y": round(bb.min.Y, 4), "z": round(bb.min.Z, 4)},
            "max": {"x": round(bb.max.X, 4), "y": round(bb.max.Y, 4), "z": round(bb.max.Z, 4)},
            "size": {
                "x": round(bb.max.X - bb.min.X, 4),
                "y": round(bb.max.Y - bb.min.Y, 4),
                "z": round(bb.max.Z - bb.min.Z, 4),
            },
        }
    except Exception as e:
        logger.debug("Could not get bounding_box: %s", e)
        props["bounding_box"] = None

    try:
        props["volume"] = round(shape.volume, 4)
    except Exception as e:
        logger.debug("Could not get volume: %s", e)
        props["volume"] = None

    try:
        props["area"] = round(shape.area, 4)
    except Exception as e:
        logger.debug("Could not get area: %s", e)
        props["area"] = None

    # Topology counts
    for attr, label in [
        ("faces", "face_count"),
        ("edges", "edge_count"),
        ("vertices", "vertex_count"),
        ("solids", "solid_count"),
        ("shells", "shell_count"),
    ]:
        try:
            items = getattr(shape, attr, None)
            if items is not None:
                if callable(items):
                    props[label] = len(items())
                else:
                    props[label] = len(items)
        except Exception as e:
            logger.debug("Could not get %s: %s", label, e)
            props[label] = None

    return props


def export_stl(
    shape: Any,
    file_path: str | Path,
    tolerance: float = 0.001,
    angular_tolerance: float = 0.1,
) -> Path:
    """Export a build123d shape to STL format.

    Args:
        shape: A build123d shape object.
        file_path: Output file path.
        tolerance: Linear deflection tolerance for mesh generation.
        angular_tolerance: Angular deflection tolerance.

    Returns:
        The resolved output path.
    """
    from build123d import export_stl as b3d_export_stl

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    b3d_export_stl(shape, str(path), tolerance=tolerance, angular_tolerance=angular_tolerance)
    logger.info("Exported STL to %s (tolerance=%s)", path, tolerance)
    return path


def export_step(shape: Any, file_path: str | Path) -> Path:
    """Export a build123d shape to STEP format.

    Args:
        shape: A build123d shape object.
        file_path: Output file path.

    Returns:
        The resolved output path.
    """
    from build123d import export_step as b3d_export_step

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    b3d_export_step(shape, str(path))
    logger.info("Exported STEP to %s", path)
    return path


def properties_summary(shape: Any) -> str:
    """Return a human-readable summary of model properties."""
    props = get_model_properties(shape)
    lines = []

    if props.get("bounding_box"):
        bb = props["bounding_box"]
        sz = bb["size"]
        lines.append(f"Size: {sz['x']} x {sz['y']} x {sz['z']} mm")

    if props.get("volume") is not None:
        lines.append(f"Volume: {props['volume']} mm³")

    if props.get("area") is not None:
        lines.append(f"Surface area: {props['area']} mm²")

    counts = []
    for label, key in [
        ("faces", "face_count"),
        ("edges", "edge_count"),
        ("vertices", "vertex_count"),
        ("solids", "solid_count"),
    ]:
        if props.get(key) is not None:
            counts.append(f"{props[key]} {label}")
    if counts:
        lines.append(f"Topology: {', '.join(counts)}")

    return "\n".join(lines) if lines else "No properties available."
