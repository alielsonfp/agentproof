"""Tests for the MCP server, through a real MCP client connected in memory."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from mcp import Client
from test_cli import write_suite

from agentproof.mcp_server import server


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project folder with one suite. The server only sees paths inside it."""
    monkeypatch.chdir(tmp_path)
    write_suite(tmp_path)
    return tmp_path


def call(tool: str, **arguments: Any) -> Any:
    async def go() -> Any:
        async with Client(server) as client:
            return await client.call_tool(tool, arguments)

    return asyncio.run(go())


def test_server_lists_the_four_tools() -> None:
    async def go() -> list[str]:
        async with Client(server) as client:
            return [tool.name for tool in (await client.list_tools()).tools]

    assert sorted(asyncio.run(go())) == [
        "compare_versions",
        "get_report",
        "list_cases",
        "run_suite",
    ]


def test_list_cases(project: Path) -> None:
    result = call("list_cases", suite_path="suite.yaml")

    assert result.is_error is False
    assert result.structured_content["name"] == "demo"
    assert result.structured_content["cases"] == [
        {
            "id": "greeting",
            "description": "Says hello.",
            "severity": "low",
            "rules": ["must_not_contain"],
        }
    ]


def test_run_suite_saves_the_run_and_returns_a_summary(project: Path) -> None:
    result = call("run_suite", suite_path="suite.yaml", out_dir="runs/v1")

    summary = result.structured_content
    assert result.is_error is False
    assert summary["run_dir"] == "runs/v1"
    assert (summary["passed"], summary["total"]) == (1, 1)
    assert summary["cases"][0]["status"] == "PASS"
    assert (project / "runs" / "v1" / "summary.json").exists()


def test_failed_cases_say_why(project: Path) -> None:
    write_suite(project, message="quero pagar com Pix")

    result = call("run_suite", suite_path="suite.yaml", out_dir="out")

    case = result.structured_content["cases"][0]
    assert case["status"] == "FAIL"
    assert case["failures"] == ["must_not_contain: turn 1 contains 'Pix'"]


def test_get_report_as_summary_and_markdown(project: Path) -> None:
    call("run_suite", suite_path="suite.yaml", out_dir="out")

    summary = call("get_report", run_dir="out").structured_content["result"]
    markdown = call("get_report", run_dir="out", format="markdown")

    assert summary["passed"] == 1
    assert markdown.content[0].text.startswith("# AgentProof report: demo")


def test_compare_versions_finds_regressions(project: Path) -> None:
    call("run_suite", suite_path="suite.yaml", prompt_version="v1", out_dir="v1")
    write_suite(project, message="quero pagar com Pix")
    call("run_suite", suite_path="suite.yaml", prompt_version="v2", out_dir="v2")

    result = call("compare_versions", base_run_dir="v1", new_run_dir="v2")

    comparison = result.structured_content
    assert comparison["has_regressions"] is True
    assert comparison["regressed"] == 1
    assert comparison["changes"][0]["change"] == "regressed"


def test_user_errors_come_back_as_readable_tool_errors(project: Path) -> None:
    result = call("list_cases", suite_path="missing.yaml")

    assert result.is_error is True
    assert "cannot read file" in result.content[0].text


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("list_cases", {"suite_path": "../other/suite.yaml"}),
        ("run_suite", {"suite_path": "suite.yaml", "out_dir": "../elsewhere"}),
        ("get_report", {"run_dir": "/"}),
    ],
)
def test_paths_outside_the_project_are_refused(
    project: Path, tool: str, arguments: dict[str, str]
) -> None:
    result = call(tool, **arguments)

    assert result.is_error is True
    assert "outside the project folder" in result.content[0].text
