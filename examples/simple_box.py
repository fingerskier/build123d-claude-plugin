"""Simple box with rounded edges — basic build123d example."""

from build123d import *

# Parameters
length = 40
width = 30
height = 20
fillet_radius = 3

# Build the part
with BuildPart() as part:
    Box(length, width, height)
    fillet(part.edges(), radius=fillet_radius)

result = part.part
