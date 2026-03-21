"""Tests for the MCP server tool handlers."""

import pytest
from build123d_mcp.server import call_tool, _models


@pytest.fixture(autouse=True)
def clear_models():
    """Clear the model store before each test."""
    _models.clear()
    yield
    _models.clear()


@pytest.mark.asyncio
async def test_execute_creates_model():
    result = await call_tool("execute_build123d", {
        "code": "result = Box(10, 10, 10)",
        "model_name": "test_box",
    })
    assert len(result) == 1
    assert "created successfully" in result[0].text
    assert "test_box" in _models


@pytest.mark.asyncio
async def test_execute_security_error():
    result = await call_tool("execute_build123d", {
        "code": "import os",
        "model_name": "bad",
    })
    assert "Security error" in result[0].text
    assert "bad" not in _models


@pytest.mark.asyncio
async def test_list_models_empty():
    result = await call_tool("list_models", {})
    assert "No models" in result[0].text


@pytest.mark.asyncio
async def test_list_models_with_entries():
    await call_tool("execute_build123d", {
        "code": "result = Box(5, 5, 5)",
        "model_name": "cube",
    })
    result = await call_tool("list_models", {})
    assert "cube" in result[0].text


@pytest.mark.asyncio
async def test_get_model_info():
    await call_tool("execute_build123d", {
        "code": "result = Box(10, 20, 30)",
        "model_name": "box",
    })
    result = await call_tool("get_model_info", {"model_name": "box"})
    assert "bounding_box" in result[0].text


@pytest.mark.asyncio
async def test_delete_model():
    await call_tool("execute_build123d", {
        "code": "result = Box(5, 5, 5)",
        "model_name": "to_delete",
    })
    assert "to_delete" in _models

    result = await call_tool("delete_model", {"model_name": "to_delete"})
    assert "deleted" in result[0].text
    assert "to_delete" not in _models


@pytest.mark.asyncio
async def test_export_stl_missing_model():
    result = await call_tool("export_stl", {"model_name": "nonexistent"})
    assert "not found" in result[0].text


@pytest.mark.asyncio
async def test_export_step_missing_model():
    result = await call_tool("export_step", {"model_name": "nonexistent"})
    assert "not found" in result[0].text
