"""MCP server for build123d CAD modeling."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, ImageContent, Tool

from build123d_mcp.executor import execute_code, ExecutionError, SecurityError
from build123d_mcp.exporter import export_stl, export_step, get_model_properties, properties_summary
from build123d_mcp.renderer import render_png_base64, render_svg, save_png, save_svg

# ---------------------------------------------------------------------------
# Session state: in-memory store of named models
# ---------------------------------------------------------------------------
_models: dict[str, Any] = {}
_output_dir: Path = Path("./cad-output")


def _ensure_output_dir() -> Path:
    _output_dir.mkdir(parents=True, exist_ok=True)
    return _output_dir


def _safe_path(file_path: str) -> Path:
    """Resolve a user-provided file path safely within the output directory.

    Raises ValueError if the resolved path escapes the output directory.
    """
    out_dir = _ensure_output_dir()
    full = (out_dir / file_path).resolve()
    if not full.is_relative_to(out_dir.resolve()):
        raise ValueError(
            f"Path '{file_path}' resolves outside the output directory."
        )
    return full


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = Server("build123d")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="execute_build123d",
            description=(
                "Execute build123d Python code to create a 3D CAD model. "
                "The code should use the build123d API (all names are pre-imported). "
                "Assign the final shape to a variable named 'result', or use a "
                "BuildPart/BuildSketch context manager. The resulting shape is stored "
                "under the given model_name for later export."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code using the build123d API.",
                    },
                    "model_name": {
                        "type": "string",
                        "description": "Name to store the resulting model under.",
                    },
                },
                "required": ["code", "model_name"],
            },
        ),
        Tool(
            name="export_stl",
            description="Export a previously created model to STL (mesh) format for 3D printing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to export.",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Output file path (relative to output dir). Defaults to <model_name>.stl.",
                    },
                    "tolerance": {
                        "type": "number",
                        "description": "Mesh tolerance in mm (default 0.001).",
                        "default": 0.001,
                    },
                },
                "required": ["model_name"],
            },
        ),
        Tool(
            name="export_step",
            description="Export a previously created model to STEP format (precise CAD interchange).",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to export.",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Output file path (relative to output dir). Defaults to <model_name>.step.",
                    },
                },
                "required": ["model_name"],
            },
        ),
        Tool(
            name="render_image",
            description=(
                "Render a model as an image. Returns a base64 PNG (displayed inline) "
                "and optionally saves the file. Available views: iso, front, back, "
                "right, left, top, bottom, iso_back."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to render.",
                    },
                    "view": {
                        "type": "string",
                        "description": "View angle (default: iso).",
                        "default": "iso",
                        "enum": ["iso", "front", "back", "right", "left", "top", "bottom", "iso_back"],
                    },
                    "width": {"type": "integer", "description": "Image width (default 800).", "default": 800},
                    "height": {"type": "integer", "description": "Image height (default 600).", "default": 600},
                    "save_path": {
                        "type": "string",
                        "description": "Optional file path to save the image. Supports .png and .svg.",
                    },
                },
                "required": ["model_name"],
            },
        ),
        Tool(
            name="list_models",
            description="List all models currently stored in the session.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_model_info",
            description="Get detailed properties of a model (bounding box, volume, surface area, topology).",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model.",
                    },
                },
                "required": ["model_name"],
            },
        ),
        Tool(
            name="delete_model",
            description="Remove a model from the session.",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to delete.",
                    },
                },
                "required": ["model_name"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
    if name == "execute_build123d":
        return await _handle_execute(arguments)
    elif name == "export_stl":
        return await _handle_export_stl(arguments)
    elif name == "export_step":
        return await _handle_export_step(arguments)
    elif name == "render_image":
        return await _handle_render_image(arguments)
    elif name == "list_models":
        return await _handle_list_models(arguments)
    elif name == "get_model_info":
        return await _handle_get_model_info(arguments)
    elif name == "delete_model":
        return await _handle_delete_model(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_execute(args: dict[str, Any]) -> list[TextContent]:
    code = args["code"]
    model_name = args["model_name"]

    try:
        result = await asyncio.to_thread(execute_code, code)
    except SecurityError as e:
        return [TextContent(type="text", text=f"Security error: {e}")]
    except ExecutionError as e:
        return [TextContent(type="text", text=f"Execution error: {e}")]

    if not result.success:
        msg = f"Execution failed:\n{result.error}"
        if result.output:
            msg += f"\n\nOutput:\n{result.output}"
        return [TextContent(type="text", text=msg)]

    _models[model_name] = result.shape
    summary = properties_summary(result.shape)
    msg = f"Model '{model_name}' created successfully.\n\n{summary}"
    if result.output:
        msg += f"\n\nOutput:\n{result.output}"
    return [TextContent(type="text", text=msg)]


async def _handle_export_stl(args: dict[str, Any]) -> list[TextContent]:
    model_name = args["model_name"]
    if model_name not in _models:
        return [TextContent(type="text", text=f"Model '{model_name}' not found. Use list_models to see available models.")]

    shape = _models[model_name]
    file_path = args.get("file_path", f"{model_name}.stl")
    tolerance = args.get("tolerance", 0.001)

    try:
        full_path = _safe_path(file_path)
        result_path = await asyncio.to_thread(export_stl, shape, full_path, tolerance=tolerance)
        size_kb = result_path.stat().st_size / 1024
        return [TextContent(type="text", text=f"Exported STL to {result_path} ({size_kb:.1f} KB)")]
    except Exception as e:
        return [TextContent(type="text", text=f"Export failed: {e}")]


async def _handle_export_step(args: dict[str, Any]) -> list[TextContent]:
    model_name = args["model_name"]
    if model_name not in _models:
        return [TextContent(type="text", text=f"Model '{model_name}' not found. Use list_models to see available models.")]

    shape = _models[model_name]
    file_path = args.get("file_path", f"{model_name}.step")

    try:
        full_path = _safe_path(file_path)
        result_path = await asyncio.to_thread(export_step, shape, full_path)
        size_kb = result_path.stat().st_size / 1024
        return [TextContent(type="text", text=f"Exported STEP to {result_path} ({size_kb:.1f} KB)")]
    except Exception as e:
        return [TextContent(type="text", text=f"Export failed: {e}")]


async def _handle_render_image(args: dict[str, Any]) -> list[TextContent | ImageContent]:
    model_name = args["model_name"]
    if model_name not in _models:
        return [TextContent(type="text", text=f"Model '{model_name}' not found. Use list_models to see available models.")]

    shape = _models[model_name]
    view = args.get("view", "iso")
    width = args.get("width", 800)
    height = args.get("height", 600)
    save_path = args.get("save_path")

    try:
        b64_png = await asyncio.to_thread(render_png_base64, shape, view=view, width=width, height=height)

        results: list[TextContent | ImageContent] = [
            ImageContent(type="image", data=b64_png, mimeType="image/png"),
        ]

        if save_path:
            full_path = _safe_path(save_path)
            if save_path.endswith(".svg"):
                await asyncio.to_thread(save_svg, shape, str(full_path), view=view, width=width, height=height)
            else:
                await asyncio.to_thread(save_png, shape, str(full_path), view=view, width=width, height=height)
            results.append(TextContent(type="text", text=f"Image saved to {full_path}"))

        return results
    except Exception as e:
        return [TextContent(type="text", text=f"Render failed: {e}")]


async def _handle_list_models(args: dict[str, Any]) -> list[TextContent]:
    if not _models:
        return [TextContent(type="text", text="No models in session. Use execute_build123d to create one.")]

    lines = []
    for name, shape in _models.items():
        try:
            bb = shape.bounding_box()
            size = f"{bb.max.X - bb.min.X:.1f} x {bb.max.Y - bb.min.Y:.1f} x {bb.max.Z - bb.min.Z:.1f} mm"
        except Exception:
            size = "unknown size"
        lines.append(f"  - {name}: {size}")

    return [TextContent(type="text", text=f"Models in session ({len(_models)}):\n" + "\n".join(lines))]


async def _handle_get_model_info(args: dict[str, Any]) -> list[TextContent]:
    model_name = args["model_name"]
    if model_name not in _models:
        return [TextContent(type="text", text=f"Model '{model_name}' not found.")]

    shape = _models[model_name]
    props = get_model_properties(shape)
    return [TextContent(type="text", text=json.dumps(props, indent=2))]


async def _handle_delete_model(args: dict[str, Any]) -> list[TextContent]:
    model_name = args["model_name"]
    if model_name not in _models:
        return [TextContent(type="text", text=f"Model '{model_name}' not found.")]

    del _models[model_name]
    return [TextContent(type="text", text=f"Model '{model_name}' deleted.")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build123d MCP Server")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./cad-output",
        help="Directory for exported files (default: ./cad-output)",
    )
    args = parser.parse_args()

    global _output_dir
    _output_dir = Path(args.output_dir).resolve()

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
