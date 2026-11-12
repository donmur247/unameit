"""Test suite for UNameIt core library."""

from pathlib import Path

import pytest
from omegaconf import OmegaConf

from unameit import core
from unameit.core import UNameIt


@pytest.fixture()
def config_dir() -> Path:
    """Return configuration directory for this test."""
    return Path(__file__).parent / "configs"


@pytest.fixture()
def unameit_obj(config_dir) -> UNameIt:
    """Return unameit object from provided source directory."""
    return UNameIt(config_dir.as_posix())


@pytest.fixture()
def unameit_config(unameit_obj: UNameIt):
    """Return unameit object with loaded configuration."""
    unameit_obj.load("basics.yml")
    return unameit_obj


@pytest.fixture()
def set_os(monkeypatch: pytest.MonkeyPatch):
    """Return a helper that pins the OS name UNameIt sees for the test."""

    def _set(os_name: str) -> None:
        monkeypatch.setattr(core, "current_os", lambda: os_name)

    return _set


@pytest.fixture(autouse=True)
def linux_os(set_os) -> None:
    """Pin the OS to linux so the suite gives the same results on every host."""
    set_os("linux")


def test_unameit_obj(unameit_obj: UNameIt, config_dir: Path):
    """Test valid unameit object."""
    assert unameit_obj.config_dir == config_dir.as_posix()


def test_unameit_obj_config_dir_not_exist(config_dir: Path):
    """Test OSError when config_dir doesn't exist."""
    with pytest.raises(OSError, match="doesn't exist or not a directory"):
        UNameIt((config_dir / "nonexistent").as_posix())


def test_unameit_obj_config_dir_not_a_directory(config_dir: Path):
    """Test OSError when config_dir is not a directory."""
    with pytest.raises(OSError, match="doesn't exist or not a directory"):
        UNameIt((config_dir / "basics.yml").as_posix())


def test_unameit_obj_config_file_not_loaded(unameit_obj: UNameIt):
    """Test config_file property before any config is loaded."""
    assert unameit_obj.config_file == Path().as_posix()


def test_unameit_config_file_loaded(unameit_config: UNameIt, config_dir: Path):
    """Test config_file property after a config is loaded."""
    assert unameit_config.config_file == (config_dir / "basics.yml").as_posix()


def test_unameit_obj_config_empty(unameit_obj: UNameIt):
    """Test whether config is loaded."""
    assert unameit_obj.conf.is_empty()


def test_unameit_config_is_not_empty(unameit_config: UNameIt):
    """Test whether loaded config is not empty."""
    assert not unameit_config.conf.is_empty()


def test_unameit_config_fail_to_load(unameit_obj: UNameIt):
    """Test FileNotFoundError when loading a nonexistent config file."""
    with pytest.raises(FileNotFoundError, match="No such file or directory"):
        unameit_obj.load("nonexistent.yml")


def test_unameit_validate_no_config_loaded(unameit_obj: UNameIt):
    """Test ValueError when validating without a loaded config."""
    with pytest.raises(ValueError, match="No config loaded"):
        unameit_obj._validate()


def test_unameit_validate_no_templates_section(unameit_obj: UNameIt):
    """Test ValueError when config has no templates section."""
    unameit_obj._conf = OmegaConf.create({"tokens": {"root": {"default": "/projects"}}})
    with pytest.raises(ValueError, match="No templates section in config"):
        unameit_obj._validate()


def test_unameit_validate_no_tokens_section(unameit_obj: UNameIt):
    """Test ValueError when config has no tokens section."""
    unameit_obj._conf = OmegaConf.create(
        {"templates": {"project_root": "$root/$project"}}
    )
    with pytest.raises(ValueError, match="No tokens section in config"):
        unameit_obj._validate()


def test_unameit_validate_valid_config(unameit_config: UNameIt):
    """Test _validate() passes with a valid loaded config."""
    assert unameit_config._validate() is None


def test_unameit_build_path_project_root_with_payload(unameit_config: UNameIt):
    """Test build_path() replaces tokens with payload values."""
    result = unameit_config.build_path("project_root", {"project": "myproj"})
    assert result == "/projects/myproj"


def test_unameit_build_path_project_root_payload_overrides_default(
    unameit_config: UNameIt,
):
    """Test build_path() payload value takes precedence over token default."""
    result = unameit_config.build_path(
        "project_root", {"root": "/shows", "project": "myproj"}
    )
    assert result == "/shows/myproj"


def test_unameit_build_path_project_root_empty_payload(unameit_config: UNameIt):
    """Test build_path() with empty payload leaves token without default unresolved."""
    result = unameit_config.build_path("project_root", {})
    assert result == "/projects/$project"


def test_unameit_build_path_project_root_missing_payload_token(unameit_config: UNameIt):
    """Test build_path() leaves $project unresolved when payload doesn't provide it."""
    result = unameit_config.build_path("project_root", {"root": "/shows"})
    assert result == "/shows/$project"


def test_unameit_build_path_project_root_ignores_unknown_payload_keys(
    unameit_config: UNameIt,
):
    """Test build_path() ignores payload keys not present in template tokens."""
    result = unameit_config.build_path(
        "project_root", {"project": "myproj", "extra": "ignored"}
    )
    assert result == "/projects/myproj"


def test_unameit_build_path_project_root_non_string_payload_value(
    unameit_config: UNameIt,
):
    """Test build_path() converts non-string payload values to string."""
    result = unameit_config.build_path("project_root", {"project": 123})
    assert result == "/projects/123"


def test_unameit_build_path_unknown_template_returns_none(unameit_config: UNameIt):
    """Test build_path() returns None for a nonexistent template name."""
    assert unameit_config.build_path("nonexistent", {"project": "myproj"}) is None


def test_unameit_build_path_empty_template_name_returns_none(unameit_config: UNameIt):
    """Test build_path() returns None for an empty template name."""
    assert unameit_config.build_path("", {"project": "myproj"}) is None


def test_unameit_build_path_empty_template_value_returns_none(unameit_config: UNameIt):
    """Test build_path() returns None for a template defined with an empty value."""
    assert unameit_config.build_path("empty_template", {"project": "myproj"}) is None


def test_unameit_extract_path_project_root(unameit_config: UNameIt):
    """Test extract_path() unpacks tokens from a path built by build_path()."""
    path = unameit_config.build_path("project_root", {"project": "GODZILLA"})
    assert unameit_config.extract_path("project_root", path) == {
        "root": "/projects",
        "project": "GODZILLA",
    }


def test_unameit_extract_path_project_root_docstring_example(unameit_config: UNameIt):
    """Test extract_path() matches the example in its docstring."""
    assert unameit_config.extract_path("project_root", "/projects/superdude") == {
        "root": "/projects",
        "project": "superdude",
    }


def test_unameit_extract_path_unknown_template_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict for a nonexistent template name."""
    assert unameit_config.extract_path("nonexistent", "/projects/GODZILLA") == {}


def test_unameit_extract_path_empty_template_value_returns_empty(
    unameit_config: UNameIt,
):
    """Test extract_path() returns empty dict for a template with an empty value."""
    assert unameit_config.extract_path("empty_template", "/projects/GODZILLA") == {}


def test_unameit_extract_path_extra_segments_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict when the path has extra segments."""
    assert unameit_config.extract_path("project_root", "/projects/GODZILLA/extra") == {}


def test_unameit_extract_path_missing_segments_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict when the path has missing segments."""
    assert unameit_config.extract_path("project_root", "/projects") == {}


def test_unameit_extract_path_pattern_mismatch_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict when a value violates the token pattern."""
    assert unameit_config.extract_path("project_root", "/projects/GOD ZILLA") == {}


def test_unameit_extract_path_token_without_pattern_falls_back(unameit_config: UNameIt):
    """Test extract_path() matches any path segment for tokens without a pattern."""
    unameit_config._templates["episode"] = "$root/$episode"
    assert unameit_config.extract_path("episode", "/projects/e01") == {
        "root": "/projects",
        "episode": "e01",
    }


@pytest.mark.parametrize(
    ("os_name", "expected"),
    [
        ("linux", "/projects/GODZILLA"),
        ("macos", "/projects/GODZILLA"),
        ("windows", "P:/GODZILLA"),
        ("freebsd", "/projects/GODZILLA"),  # no matching key, falls back to default
    ],
)
def test_unameit_build_path_root_per_os(
    unameit_config: UNameIt, set_os, os_name: str, expected: str
):
    """Test build_path() uses the root for the current OS, or default if none is set."""
    set_os(os_name)
    assert (
        unameit_config.build_path("project_root", {"project": "GODZILLA"}) == expected
    )


def test_unameit_build_path_payload_overrides_os_root(unameit_config: UNameIt, set_os):
    """Test payload root takes precedence over the OS-specific root."""
    set_os("windows")
    result = unameit_config.build_path(
        "project_root", {"root": "/shows", "project": "GODZILLA"}
    )
    assert result == "/shows/GODZILLA"


@pytest.mark.parametrize(
    ("root", "expected"),
    [
        ("P:", "P:/GODZILLA"),
        ("P:/", "P:/GODZILLA"),
        ("P://", "P:/GODZILLA"),
        ("//server/share", "//server/share/GODZILLA"),
        ("", "/GODZILLA"),
        ("/", "/GODZILLA"),
    ],
)
def test_unameit_build_path_os_root_slashes(
    unameit_config: UNameIt, set_os, root: str, expected: str
):
    """Test extra slashes at the root/template boundary are removed, UNC kept."""
    set_os("windows")
    unameit_config._tokens.root.os.windows = root
    assert (
        unameit_config.build_path("project_root", {"project": "GODZILLA"}) == expected
    )


def test_unameit_build_path_null_os_value_falls_back_to_default(
    unameit_config: UNameIt, set_os
):
    """Test a null OS value is treated as unset and falls back to default."""
    set_os("linux")
    unameit_config._tokens.root.os.linux = None
    assert unameit_config.build_path("project_root", {"project": "GODZILLA"}) == (
        "/projects/GODZILLA"
    )


def test_unameit_extract_path_windows_root(unameit_config: UNameIt, set_os):
    """Test extract_path() matches the root for the current OS (windows)."""
    set_os("windows")
    assert unameit_config.extract_path("project_root", "P:/GODZILLA") == {
        "root": "P:",
        "project": "GODZILLA",
    }


def test_unameit_extract_path_other_os_root_not_matched(unameit_config: UNameIt):
    """Test extract_path() only matches the current OS root (linux here)."""
    assert unameit_config.extract_path("project_root", "P:/GODZILLA") == {}


def test_unameit_extract_path_empty_os_root(unameit_config: UNameIt, set_os):
    """Test extract_path() matches an empty root."""
    set_os("linux")
    unameit_config._tokens.root.os.linux = ""
    assert unameit_config.extract_path("project_root", "/GODZILLA") == {
        "root": "",
        "project": "GODZILLA",
    }


@pytest.mark.parametrize("os_name", ["linux", "macos", "windows"])
def test_unameit_build_extract_round_trip(
    unameit_config: UNameIt, set_os, os_name: str
):
    """Test extracting a built path and building again gives the same path."""
    set_os(os_name)
    path = unameit_config.build_path("project_root", {"project": "GODZILLA"})
    data = unameit_config.extract_path("project_root", path)
    assert unameit_config.build_path("project_root", data) == path


def _set_tokens(unameit_obj: UNameIt, tokens: dict) -> None:
    """Replace the loaded config with one using the given tokens section."""
    unameit_obj._conf = OmegaConf.create(
        {"tokens": tokens, "templates": {"project_root": "$root/$project"}}
    )


def test_unameit_validate_token_not_mapping(unameit_obj: UNameIt):
    """Test ValueError when a token is not a mapping."""
    _set_tokens(unameit_obj, {"root": "/projects"})
    with pytest.raises(TypeError, match="Token 'root' must be a mapping"):
        unameit_obj._validate()


def test_unameit_validate_os_not_mapping(unameit_obj: UNameIt):
    """Test ValueError when `os` is not a mapping."""
    _set_tokens(unameit_obj, {"root": {"os": "P:"}})
    with pytest.raises(TypeError, match="'os' of token 'root' must be a mapping"):
        unameit_obj._validate()


def test_unameit_validate_unknown_os_key(unameit_obj: UNameIt):
    """Test ValueError for an unknown OS key, such as a typo."""
    _set_tokens(unameit_obj, {"root": {"os": {"windoes": "P:"}}})
    with pytest.raises(ValueError, match="Unknown OS 'windoes'"):
        unameit_obj._validate()


def test_unameit_validate_os_value_not_string(unameit_obj: UNameIt):
    """Test ValueError when an OS value is not a string."""
    _set_tokens(unameit_obj, {"root": {"os": {"windows": 123}}})
    with pytest.raises(ValueError, match="must be a string"):
        unameit_obj._validate()


def test_unameit_validate_os_allows_empty_and_null(unameit_obj: UNameIt):
    """Test empty and null OS values are accepted."""
    _set_tokens(
        unameit_obj, {"root": {"os": {"linux": "", "windows": "P:", "macos": None}}}
    )
    assert unameit_obj._validate() is None
