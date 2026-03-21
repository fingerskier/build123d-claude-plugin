# Build123d CAD Modeling Plugin

This project provides an MCP server for creating 3D CAD models using **build123d**, a Python parametric CAD library built on the OpenCascade kernel.

## MCP Tools Available

Use these tools to create and export CAD models:

- **`execute_build123d`** — Run build123d Python code to create a 3D model. All build123d names are pre-imported. Store the result in a variable named `result` or use a `BuildPart` context manager.
- **`export_stl`** — Export a model to STL format (triangulated mesh, for 3D printing).
- **`export_step`** — Export a model to STEP format (precise BREP, for CAD interchange).
- **`render_image`** — Render a model to a PNG image (views: iso, front, back, right, left, top, bottom).
- **`list_models`** — List all models in the current session.
- **`get_model_info`** — Get detailed properties (bounding box, volume, surface area, topology).
- **`delete_model`** — Remove a model from the session.

## Build123d Quick Reference

### Two API Modes

**Builder Mode** — uses context managers, state accumulates:
```python
with BuildPart() as part:
    Box(10, 20, 5)
    with BuildSketch(part.faces().sort_by(Axis.Z)[-1]):
        Circle(3)
    extrude(amount=-2, mode=Mode.SUBTRACT)
result = part.part
```

**Algebra Mode** — uses operators, stateless:
```python
box = Box(10, 20, 5)
hole = Pos(0, 0, 5) * Cylinder(3, 10)
result = box - hole
```

### Common 3D Shapes
| Shape | Parameters |
|-------|-----------|
| `Box(length, width, height)` | Centered at origin |
| `Cylinder(radius, height)` | Along Z axis |
| `Sphere(radius)` | Centered at origin |
| `Cone(bottom_radius, top_radius, height)` | Along Z axis |
| `Torus(major_radius, minor_radius)` | In XY plane |
| `Wedge(xsize, ysize, zsize, xmin, zmin, xmax, zmax)` | Wedge/ramp shape |

### Common 2D Sketch Shapes
| Shape | Parameters |
|-------|-----------|
| `Circle(radius)` | Centered at origin |
| `Rectangle(width, height)` | Centered at origin |
| `RegularPolygon(radius, side_count)` | Regular polygon |
| `Polygon(points)` | From list of (x,y) tuples |
| `Text(text, font_size)` | Text outline |
| `SlotOverall(width, height)` | Slot/stadium shape |
| `Ellipse(x_radius, y_radius)` | Ellipse |

### Key Operations
| Operation | Description |
|-----------|-------------|
| `extrude(amount=N)` | Extrude sketch into 3D |
| `revolve(axis=Axis.X, revolution_arc=360)` | Revolve sketch around axis |
| `fillet(edges, radius=R)` | Round edges |
| `chamfer(edges, length=L)` | Bevel edges |
| `loft(sections=[s1, s2])` | Loft between sections |
| `sweep(path=wire)` | Sweep section along path |
| `offset(amount=N)` | Offset/shell a shape |
| `mirror(about=Plane.XZ)` | Mirror geometry |
| `split(bisect_by=Plane.XZ)` | Split shape with plane |
| `shell(faces, thickness)` | Hollow out a solid |

### Boolean Operations
- **Builder mode**: Use `mode=Mode.ADD` (default), `mode=Mode.SUBTRACT`, `mode=Mode.INTERSECT`
- **Algebra mode**: Use `+` (union), `-` (subtract), `&` (intersect)

### Positioning and Transformation
```python
# Translate
Pos(x, y, z) * shape

# Rotate
Rot(rx, ry, rz) * shape

# On a specific plane
Plane.XZ * shape

# Locate on a face
with BuildSketch(part.faces().sort_by(Axis.Z)[-1]):
    ...
```

### Selecting Faces and Edges
```python
# Sort by axis position
part.faces().sort_by(Axis.Z)[-1]    # Top face
part.faces().sort_by(Axis.Z)[0]     # Bottom face

# Filter by type
part.edges().filter_by(GeomType.LINE)
part.edges().filter_by(GeomType.CIRCLE)

# Filter by direction/axis
part.edges().filter_by(Axis.Z)      # Edges parallel to Z

# Group and select
part.edges().group_by(Axis.Z)[-1]   # Top edges
```

### Patterns and Arrays
```python
# Linear pattern
with Locations(GridLocations(x_spacing, y_spacing, x_count, y_count)):
    Hole(radius, depth)

# Polar/circular pattern
with PolarLocations(radius, count):
    Hole(radius, depth)
```

## Best Practices

1. **Work 2D before 3D** — Create sketches first, then extrude/revolve
2. **Parameterize dimensions** — Use variables for key measurements
3. **Delay fillets/chamfers** — Apply after all boolean operations
4. **Name your result** — Assign the final shape to `result`
5. **Use Builder mode for complex parts** — Context managers manage state automatically
6. **Use Algebra mode for simple combinations** — Cleaner for basic boolean ops

## Code Template

When writing build123d code for `execute_build123d`, use this pattern:

```python
# All build123d names are pre-imported (Box, Cylinder, BuildPart, etc.)
# math module is also available

# Define parameters
width = 50
height = 30
wall_thickness = 2

# Build the model
with BuildPart() as part:
    Box(width, height, 10)
    # ... additional operations

result = part.part
```

## Export Guidelines

- **STL** — Use for 3D printing. Set tolerance lower (0.0005) for fine detail, higher (0.01) for faster/smaller files.
- **STEP** — Use for sharing with other CAD software. Preserves exact geometry.
- **Images** — Use `render_image` with different views (iso, front, top) to visualize from multiple angles.
