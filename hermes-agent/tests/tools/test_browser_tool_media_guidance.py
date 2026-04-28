"""Regression tests for browser_tool media guidance text."""

from tools import browser_tool


def test_browser_vision_description_avoids_literal_placeholder_media_tag():
    browser_vision = next(
        tool for tool in browser_tool.BROWSER_TOOL_SCHEMAS
        if tool.get("name") == "browser_vision"
    )

    description = browser_vision["description"]
    assert "MEDIA:<screenshot_path>" not in description
    assert "returned screenshot_path value" in description
