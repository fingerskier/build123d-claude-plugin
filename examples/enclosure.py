"""Parametric electronics enclosure with lid — intermediate build123d example."""

from build123d import *

# Parameters
inner_width = 60
inner_depth = 40
inner_height = 25
wall = 2
corner_radius = 3
screw_hole_radius = 1.5
screw_inset = 5
lid_height = 5

# --- Bottom shell ---
with BuildPart() as bottom:
    # Outer box
    Box(inner_width + 2 * wall, inner_depth + 2 * wall, inner_height + wall)
    # Round vertical edges
    fillet(bottom.edges().filter_by(Axis.Z), radius=corner_radius)
    # Hollow out (shell from top face)
    top_face = bottom.faces().sort_by(Axis.Z)[-1]
    shell(top_face, amount=-wall)
    # Screw mounting holes in corners
    with BuildSketch(bottom.faces().sort_by(Axis.Z)[-1]):
        with Locations([
            (inner_width / 2 - screw_inset, inner_depth / 2 - screw_inset),
            (-inner_width / 2 + screw_inset, inner_depth / 2 - screw_inset),
            (inner_width / 2 - screw_inset, -inner_depth / 2 + screw_inset),
            (-inner_width / 2 + screw_inset, -inner_depth / 2 + screw_inset),
        ]):
            Circle(screw_hole_radius)
    extrude(amount=-inner_height, mode=Mode.SUBTRACT)

result = bottom.part
