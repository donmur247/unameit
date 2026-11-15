"""Test suite for UNameIt utility functions."""

import types

import pytest

from unameit import util


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("win32", "windows"),
        ("linux", "linux"),
        ("darwin", "macos"),
        ("freebsd", "freebsd"),
    ],
)
def test_current_os_maps_sys_platform(monkeypatch, platform: str, expected: str):
    """Test current_os() maps sys.platform to the OS keys used in config."""
    monkeypatch.setattr(util, "sys", types.SimpleNamespace(platform=platform))
    assert util.current_os() == expected


@pytest.mark.parametrize(
    ("value", "has_lead", "has_trail", "expected"),
    [
        ("P:/", False, True, "P:"),
        ("P://", False, True, "P:"),
        ("/projects", True, False, "projects"),
        ("//server/share/", False, True, "//server/share"),
        ("/projects", False, False, "/projects"),
        ("P:/", False, False, "P:/"),
    ],
)
def test_strip_boundary_slashes(
    value: str, has_lead: bool, has_trail: bool, expected: str
):
    """Test only the slashes the template provides are removed from a value."""
    assert util.strip_boundary_slashes(value, has_lead, has_trail) == expected


@pytest.mark.parametrize(
    ("text", "token", "value", "expected"),
    [
        ("@{root}/@{project}", "root", "/projects", "/projects/@{project}"),
        ("@{root}/@{project}", "root", "P:/", "P:/@{project}"),
        ("@{root}/@{project}", "root", "P://", "P:/@{project}"),
        ("/@{root}/@{project}", "root", "/projects", "/projects/@{project}"),
        ("@{root}/@{project}", "project", "MYPUPPIES", "@{root}/MYPUPPIES"),
        ("@{root}@{project}", "root", "P:/", "P:/@{project}"),
        ("@{root_dir}/@{root}", "root", "/projects", "@{root_dir}/projects"),
        ("@{root_dir}/@{root}", "root_dir", "/x", "/x/@{root}"),
        ("@{task}_@{task_description}", "task", "model", "model_@{task_description}"),
        ("@{task}_@{task_description}", "task_description", "main", "@{task}_main"),
        ("@{shot}_01", "shot", "sh010", "sh010_01"),
        ("no tokens here", "root", "x", "no tokens here"),
    ],
)
def test_substitute_token(text: str, token: str, value: str, expected: str):
    """Test whole-token replacement with slashes normalized at template boundaries."""
    assert util.substitute_token(text, token, value) == expected


def test_find_tokens_from_template():
    """Test tokens are found by the @{} syntax, longest first."""
    template = "@{root}/@{project}/some/path/@{filename}.@{ext}"
    assert util.find_tokens_from_template(template) == [
        "filename",
        "project",
        "root",
        "ext",
    ]


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("@{task}_@{task_description}", ["task_description", "task"]),
        ("@{shot}_01", ["shot"]),
        ("@{task_}", ["task_"]),
        ("@root/@project", []),
        ("$root/$project", []),
        ("${templates.project_root}/assets", []),
        ("@{}", []),
        ("@{ root }", []),
        ("@{root", []),
    ],
)
def test_find_tokens_from_template_syntax(template: str, expected: list[str]):
    """Test only @{name} is a token; bare @name, $name, ${...} and malformed braces are text."""
    assert util.find_tokens_from_template(template) == expected


def test_substitute_tokens_single_pass():
    """Test values are substituted in one pass, so substituted text is never re-scanned."""
    values = {"task": "model", "task_description": "main"}
    assert util.substitute_tokens("@{task}_@{task_description}", values) == "model_main"
    assert util.substitute_tokens("@{a}@{b}", {"a": "@{b}", "b": "x"}) == "@{b}x"
    assert util.substitute_tokens("@{a}@{b}", {"a": "x"}) == "x@{b}"
