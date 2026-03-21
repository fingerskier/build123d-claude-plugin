# build123d-claude-plugin

A Claude Code plugin and MCP server for creating 3D CAD models using [build123d](https://github.com/gumyr/build123d), a Python parametric CAD library built on the OpenCascade kernel.

## Features

- **AI-assisted CAD modeling** — Claude writes build123d code, executes it, and exports artifacts
- **MCP server** with 7 tools for the full CAD workflow:
  - `execute_build123d` — Run build123d code to create 3D models
  - `export_stl` — Export to STL (for 3D printing)
  - `export_step` — Export to STEP (for CAD interchange)
  - `render_image` — Render PNG/SVG images from multiple view angles
  - `list_models` / `get_model_info` / `delete_model` — Session management
- **Sandboxed execution** — Code runs in a restricted namespace (no filesystem/network access)
- **CLAUDE.md** reference — Comprehensive build123d API guide for Claude

## Installation

```bash
pip install -e .
```

### Dependencies

- Python 3.10+
- [build123d](https://github.com/gumyr/build123d) (and OpenCascade via cadquery-ocp)
- [mcp](https://pypi.org/project/mcp/) (Model Context Protocol SDK)
- [CairoSVG](https://cairosvg.org/) (optional, for PNG rendering)
- [Pillow](https://pillow.readthedocs.io/) (fallback image support)

## Setup with Claude Code

Add the MCP server to your Claude Code configuration:

```json
{
  "mcpServers": {
    "build123d": {
      "command": "build123d-mcp",
      "args": ["--output-dir", "./cad-output"]
    }
  }
}
```

Or run from source:

```json
{
  "mcpServers": {
    "build123d": {
      "command": "python",
      "args": ["-m", "build123d_mcp.server", "--output-dir", "./cad-output"]
    }
  }
}
```

## Usage

Once configured, ask Claude to create CAD models:

> "Create a box with rounded edges, 40x30x20mm with 3mm fillets"

> "Design a parametric enclosure for a Raspberry Pi with screw mounting holes"

> "Make an L-bracket with mounting holes and export it as STL for 3D printing"

Claude will:
1. Write build123d code using the `execute_build123d` tool
2. Show you model properties (size, volume, topology)
3. Render images with `render_image`
4. Export to STL/STEP when you're ready

## Project Structure

```
├── CLAUDE.md                      # Build123d reference for Claude
├── pyproject.toml                 # Python package config
├── src/build123d_mcp/
│   ├── server.py                  # MCP server & tool definitions
│   ├── executor.py                # Sandboxed code execution engine
│   ├── exporter.py                # STL/STEP export + model properties
│   └── renderer.py                # SVG/PNG image rendering
├── examples/                      # Example build123d scripts
│   ├── simple_box.py
│   ├── enclosure.py
│   └── bracket.py
└── tests/                         # Unit tests
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

## Security

The code executor enforces these constraints:
- **Allowed imports**: `build123d`, `math`, `typing`, `collections`, `itertools`, `functools`, `dataclasses`, `enum`
- **Blocked builtins**: `open`, `exec`, `eval`, `__import__`, `compile`, `exit`, `input`, and others
- **AST validation**: Dangerous patterns (disallowed imports, dunder access) are rejected before execution
- **Timeout**: 60-second execution limit

## License

MIT
