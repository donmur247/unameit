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
        ("@root/@project", "root", "/projects", "/projects/@project"),
        ("@root/@project", "root", "P:/", "P:/@project"),
        ("@root/@project", "root", "P://", "P:/@project"),
        ("/@root/@project", "root", "/projects", "/projects/@project"),
        ("@root/@project", "project", "MYPUPPIES", "@root/MYPUPPIES"),
        ("@root@project", "root", "P:/", "P:/@project"),
        ("@root_dir/@root", "root", "/projects", "@root_dir/projects"),
        ("@root_dir/@root", "root_dir", "/x", "/x/@root"),
        ("no tokens here", "root", "x", "no tokens here"),
    ],
)
def test_substitute_token(text: str, token: str, value: str, expected: str):
    """Test whole-token replacement with slashes normalized at template boundaries."""
    assert util.substitute_token(text, token, value) == expected


def test_find_tokens_from_template():
    """Test tokens are found by the @ prefix, longest first, and $ is not a token."""
    template = "@root/@project/some/path/@filename.@ext"
    assert util.find_tokens_from_template(template) == [
        "filename",
        "project",
        "root",
        "ext",
    ]
    assert util.find_tokens_from_template("$root/$project") == []
    assert util.find_tokens_from_template("${templates.project_root}/assets") == []
