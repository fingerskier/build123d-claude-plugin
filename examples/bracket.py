"""L-bracket with mounting holes and fillets — intermediate build123d example."""

from build123d import *
import math

# Parameters
base_length = 50
base_width = 30
base_thickness = 5
wall_height = 40
wall_thickness = 5
fillet_radius = 8
hole_diameter = 6
hole_count_base = 2
hole_count_wall = 2
hole_inset = 12

# Build the L-bracket
with BuildPart() as bracket:
    # Base plate
    with BuildSketch():
        Rectangle(base_length, base_width)
    extrude(amount=base_thickness)

    # Vertical wall
    with BuildSketch(bracket.faces().sort_by(Axis.Z)[-1]):
        with Locations([(0, -base_width / 2 + wall_thickness / 2)]):
            Rectangle(base_length, wall_thickness)
    extrude(amount=wall_height)

    # Fillet the inner corner where wall meets base
    inner_edges = (
        bracket.edges()
        .filter_by(Axis.X)
        .sort_by(Axis.Y)[-2:]  # Inner edges along X
        .sort_by(Axis.Z)[0:1]  # Bottom-most
    )
    fillet(inner_edges, radius=fillet_radius)

    # Base mounting holes
    with BuildSketch(bracket.faces().sort_by(Axis.Z)[0]):
        with Locations([
            (-base_length / 2 + hole_inset, base_width / 4),
            (base_length / 2 - hole_inset, base_width / 4),
        ]):
            Circle(hole_diameter / 2)
    extrude(amount=base_thickness, mode=Mode.SUBTRACT)

    # Wall mounting holes
    back_face = bracket.faces().sort_by(Axis.Y)[0]
    with BuildSketch(back_face):
        with Locations([
            (-base_length / 2 + hole_inset, wall_height / 2),
            (base_length / 2 - hole_inset, wall_height / 2),
        ]):
            Circle(hole_diameter / 2)
    extrude(amount=-wall_thickness, mode=Mode.SUBTRACT)

result = bracket.part
