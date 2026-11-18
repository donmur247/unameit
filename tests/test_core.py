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
        {"templates": {"project_root": "@{root}/@{project}"}}
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
    assert result == "/projects/@{project}"


def test_unameit_build_path_project_root_missing_payload_token(unameit_config: UNameIt):
    """Test build_path() leaves @{project} unresolved when payload doesn't provide it."""
    result = unameit_config.build_path("project_root", {"root": "/shows"})
    assert result == "/shows/@{project}"


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


def test_unameit_build_path_task_type_underscore_is_literal(unameit_config: UNameIt):
    """Test an underscore before a token is literal, so @{task}_@{task_description} works."""
    payload = {"task": "model", "task_description": "main"}
    assert unameit_config.build_path("task_type", payload) == "model_main"


def test_unameit_build_path_work_dcc_root_task_type(unameit_config: UNameIt):
    """Test a nested template that interpolates task_type resolves all its tokens."""
    payload = {
        "project": "MYPUPPIES",
        "asset_category": "chr",
        "asset_name": "shaggyDog",
        "task": "model",
        "task_description": "main",
        "dcc": "maya",
    }
    assert unameit_config.build_path("assets.work_dcc_root", payload) == (
        "/projects/MYPUPPIES/assets/chr/shaggyDog/main/work/model_main/maya"
    )


def test_unameit_build_path_token_followed_by_literal_text(unameit_config: UNameIt):
    """Test a braced token can be followed directly by literal text, e.g. @{shot}_01."""
    unameit_config._templates["shot_code"] = "@{shot}_01"
    assert unameit_config.build_path("shot_code", {"shot": "sh010"}) == "sh010_01"


def test_unameit_extract_path_token_followed_by_literal_text(unameit_config: UNameIt):
    """Test extract_path() reads a braced token followed by literal text."""
    unameit_config._templates["shot_code"] = "@{shot}_01"
    assert unameit_config.extract_path("shot_code", "sh010_01") == {"shot": "sh010"}


def test_unameit_build_path_bare_token_is_literal(unameit_config: UNameIt):
    """Test bare @name is not a token, so a template without braces returns None."""
    unameit_config._templates["bare"] = "@root/@project"
    assert unameit_config.build_path("bare", {"project": "MYPUPPIES"}) is None


def test_unameit_build_path_optional_token_provided(unameit_config: UNameIt):
    """Test an optional group is kept, without its brackets, when its token is provided."""
    payload = {
        "material_name": "brick",
        "channel_name": "diffuse",
        "udim": "1001",
        "extension": ".exr",
    }
    result = unameit_config.build_path("assets.texture_name", payload)
    assert result == "brick_diffuse.1001.exr"


def test_unameit_build_path_optional_token_missing(unameit_config: UNameIt):
    """Test an optional group is removed, dots included, when its token is missing."""
    payload = {"material_name": "brick", "channel_name": "diffuse", "extension": ".exr"}
    result = unameit_config.build_path("assets.texture_name", payload)
    assert result == "brick_diffuse.exr"


def test_unameit_build_path_optional_token_uses_default(unameit_config: UNameIt):
    """Test an optional group is kept when its token has a default value."""
    unameit_config._templates["variant_tag"] = "@{material_name}[_@{asset_variant}]"
    result = unameit_config.build_path("variant_tag", {"material_name": "brick"})
    assert result == "brick_main"
    payload = {"material_name": "brick", "asset_variant": "dirty"}
    assert unameit_config.build_path("variant_tag", payload) == "brick_dirty"


def test_unameit_build_path_literal_brackets(unameit_config: UNameIt):
    """Test brackets without a token are literal text."""
    unameit_config._templates["literal"] = "@{material_name}[raw]"
    assert unameit_config.build_path("literal", {"material_name": "brick"}) == "brick[raw]"


def test_unameit_build_path_optional_segment_between_slashes(unameit_config: UNameIt):
    """Test a dropped optional segment between slashes leaves a single slash."""
    unameit_config._templates["segment_path"] = "@{root}/[@{shot}]/@{name}"
    assert unameit_config.build_path("segment_path", {"name": "x"}) == "/projects/x"
    payload = {"shot": "sh010", "name": "x"}
    assert unameit_config.build_path("segment_path", payload) == "/projects/sh010/x"


def test_unameit_extract_path_optional_token_matched(unameit_config: UNameIt):
    """Test an optional token is extracted when it is present in the path."""
    result = unameit_config.extract_path("assets.texture_name", "brick_diffuse.1001.exr")
    assert result == {
        "material_name": "brick",
        "channel_name": "diffuse",
        "udim": "1001",
        "extension": ".exr",
    }


def test_unameit_extract_path_optional_token_not_matched(unameit_config: UNameIt):
    """Test an optional token is left out of the result when it is absent from the path."""
    result = unameit_config.extract_path("assets.texture_name", "brick_diffuse.exr")
    assert result == {
        "material_name": "brick",
        "channel_name": "diffuse",
        "extension": ".exr",
    }


def test_unameit_extract_path_optional_token_bad_value_returns_empty(
    unameit_config: UNameIt,
):
    """Test a value that doesn't fit the optional group fails the whole match."""
    assert unameit_config.extract_path("assets.texture_name", "brick_diffuse.10.exr") == {}


def test_unameit_extract_path_not_exact_optional_token(unameit_config: UNameIt):
    """Test exact=False extracts an optional token and reports the leftover element."""
    result = unameit_config.extract_path(
        "assets.texture_name", "brick_diffuse.exr/extra", exact=False
    )
    assert result == {
        "material_name": "brick",
        "channel_name": "diffuse",
        "extension": ".exr",
        "not_matched": ["extra"],
    }


def test_unameit_extract_path_optional_segment_between_slashes(
    unameit_config: UNameIt,
):
    """Test an optional path segment between slashes is extracted when it is present."""
    unameit_config._templates["segment_path"] = "@{root}/[@{shot}]/@{name}"
    assert unameit_config.extract_path("segment_path", "/projects/sh010/x") == {
        "root": "/projects",
        "shot": "sh010",
        "name": "x",
    }
    assert unameit_config.extract_path("segment_path", "/projects/x") == {
        "root": "/projects",
        "name": "x",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"material_name": "brick", "channel_name": "diffuse", "udim": "1001", "extension": ".exr"},
        {"material_name": "brick", "channel_name": "diffuse", "extension": ".exr"},
    ],
)
def test_unameit_optional_token_round_trip(unameit_config: UNameIt, payload: dict):
    """Test building and then extracting an optional token gives back the same payload."""
    path = unameit_config.build_path("assets.texture_name", payload)
    assert unameit_config.extract_path("assets.texture_name", path) == payload


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
    path = unameit_config.build_path("project_root", {"project": "MYPUPPIES"})
    assert unameit_config.extract_path("project_root", path) == {
        "root": "/projects",
        "project": "MYPUPPIES",
    }


def test_unameit_extract_path_project_root_docstring_example(unameit_config: UNameIt):
    """Test extract_path() matches the example in its docstring."""
    assert unameit_config.extract_path("project_root", "/projects/superdude") == {
        "root": "/projects",
        "project": "superdude",
    }


def test_unameit_build_path_nested_template(unameit_config: UNameIt):
    """Test build_path() resolves dotted names to nested templates."""
    result = unameit_config.build_path("assets.root", {"project": "MYPUPPIES"})
    assert result == "/projects/MYPUPPIES/assets"


def test_unameit_build_path_nested_relative_interpolation(unameit_config: UNameIt):
    """Test build_path() follows relative interpolations between nested templates."""
    payload = {
        "project": "MYPUPPIES",
        "asset_category": "CHARACTERS",
        "asset_name": "hero",
    }
    assert (
        unameit_config.build_path("assets.category_root", payload)
        == "/projects/MYPUPPIES/assets/CHARACTERS"
    )
    assert (
        unameit_config.build_path("assets.name_root", payload)
        == "/projects/MYPUPPIES/assets/CHARACTERS/hero"
    )


@pytest.mark.parametrize("name", ["assets", "assets.missing", "project_root.foo"])
def test_unameit_build_path_non_template_name_returns_none(
    unameit_config: UNameIt, name: str
):
    """Test build_path() returns None for section names and missing nested names."""
    assert unameit_config.build_path(name, {"project": "MYPUPPIES"}) is None


def test_unameit_extract_path_nested_template(unameit_config: UNameIt):
    """Test extract_path() resolves dotted names to nested templates."""
    result = unameit_config.extract_path("assets.root", "/projects/MYPUPPIES/assets")
    assert result == {"root": "/projects", "project": "MYPUPPIES"}


@pytest.mark.parametrize("name", ["", "assets", "assets.missing"])
def test_unameit_extract_path_non_template_name_returns_empty(
    unameit_config: UNameIt, name: str
):
    """Test extract_path() returns empty dict for empty, section, or missing names."""
    assert unameit_config.extract_path(name, "/projects/MYPUPPIES") == {}


def test_unameit_extract_path_unknown_template_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict for a nonexistent template name."""
    assert unameit_config.extract_path("nonexistent", "/projects/MYPUPPIES") == {}


def test_unameit_extract_path_empty_template_value_returns_empty(
    unameit_config: UNameIt,
):
    """Test extract_path() returns empty dict for a template with an empty value."""
    assert unameit_config.extract_path("empty_template", "/projects/MYPUPPIES") == {}


def test_unameit_extract_path_extra_segments_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict when the path has extra segments."""
    assert unameit_config.extract_path("project_root", "/projects/MYPUPPIES/extra") == {}


def test_unameit_extract_path_missing_segments_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict when the path has missing segments."""
    assert unameit_config.extract_path("project_root", "/projects") == {}


def test_unameit_extract_path_pattern_mismatch_returns_empty(unameit_config: UNameIt):
    """Test extract_path() returns empty dict when a value violates the token pattern."""
    assert unameit_config.extract_path("project_root", "/projects/MY PUPPIES") == {}


def test_unameit_extract_path_token_without_pattern_falls_back(unameit_config: UNameIt):
    """Test extract_path() matches any path segment for tokens without a pattern."""
    unameit_config._templates["episode"] = "@{root}/@{episode}"
    assert unameit_config.extract_path("episode", "/projects/e01") == {
        "root": "/projects",
        "episode": "e01",
    }


def test_unameit_extract_path_not_exact_extra_elements(unameit_config: UNameIt):
    """Test exact=False extracts matched tokens and lists leftover path elements."""
    result = unameit_config.extract_path(
        "project_root", "/projects/MYPUPPIES/extra/more", exact=False
    )
    assert result == {
        "root": "/projects",
        "project": "MYPUPPIES",
        "not_matched": ["extra", "more"],
    }


def test_unameit_extract_path_not_exact_full_match_empty_not_matched(
    unameit_config: UNameIt,
):
    """Test exact=False on a full match returns an empty not_matched list."""
    result = unameit_config.extract_path(
        "project_root", "/projects/MYPUPPIES", exact=False
    )
    assert result == {
        "root": "/projects",
        "project": "MYPUPPIES",
        "not_matched": [],
    }


def test_unameit_extract_path_not_exact_missing_segments(unameit_config: UNameIt):
    """Test exact=False returns only the tokens that were found."""
    result = unameit_config.extract_path("project_root", "/projects", exact=False)
    assert result == {"root": "/projects", "not_matched": []}


def test_unameit_extract_path_not_exact_pattern_mismatch(unameit_config: UNameIt):
    """Test exact=False keeps the root and reports the invalid element as not matched."""
    result = unameit_config.extract_path(
        "project_root", "/projects/MY PUPPIES", exact=False
    )
    assert result == {"root": "/projects", "not_matched": ["MY PUPPIES"]}


def test_unameit_extract_path_not_exact_root_mismatch(unameit_config: UNameIt):
    """Test exact=False with no matching prefix returns all elements as not matched."""
    result = unameit_config.extract_path(
        "project_root", "/shows/MYPUPPIES", exact=False
    )
    assert result == {"not_matched": ["shows", "MYPUPPIES"]}


def test_unameit_extract_path_not_exact_stops_at_middle_mismatch(
    unameit_config: UNameIt,
):
    """Test exact=False stops at the first mismatch, so later tokens are not extracted."""
    unameit_config._templates["shot_path"] = "@{root}/@{project}/shots/@{shot}"
    result = unameit_config.extract_path(
        "shot_path", "/projects/MYPUPPIES/comp/sh010", exact=False
    )
    assert result == {
        "root": "/projects",
        "project": "MYPUPPIES",
        "not_matched": ["comp", "sh010"],
    }


def test_unameit_extract_path_not_exact_trailing_separator(unameit_config: UNameIt):
    """Test a trailing separator is not reported as a not matched element."""
    result = unameit_config.extract_path(
        "project_root", "/projects/MYPUPPIES/", exact=False
    )
    assert result == {
        "root": "/projects",
        "project": "MYPUPPIES",
        "not_matched": [],
    }


def test_unameit_extract_path_not_exact_windows_root(unameit_config: UNameIt, set_os):
    """Test exact=False uses the root for the current OS."""
    set_os("windows")
    result = unameit_config.extract_path(
        "project_root", "P:/MYPUPPIES/extra", exact=False
    )
    assert result == {
        "root": "P:",
        "project": "MYPUPPIES",
        "not_matched": ["extra"],
    }


def test_unameit_extract_path_not_exact_unknown_template_returns_empty(
    unameit_config: UNameIt,
):
    """Test exact=False still returns empty dict for a nonexistent template."""
    assert (
        unameit_config.extract_path("nonexistent", "/projects/MYPUPPIES", exact=False)
        == {}
    )


def test_unameit_extract_path_exact_true_returns_empty_on_extra_elements(
    unameit_config: UNameIt,
):
    """Test exact=True returns empty dict when the path has extra elements."""
    assert (
        unameit_config.extract_path(
            "project_root", "/projects/MYPUPPIES/extra", exact=True
        )
        == {}
    )


@pytest.mark.parametrize(
    ("os_name", "expected"),
    [
        ("linux", "/projects/MYPUPPIES"),
        ("macos", "/projects/MYPUPPIES"),
        ("windows", "P:/MYPUPPIES"),
        ("freebsd", "/projects/MYPUPPIES"),  # no matching key, falls back to default
    ],
)
def test_unameit_build_path_root_per_os(
    unameit_config: UNameIt, set_os, os_name: str, expected: str
):
    """Test build_path() uses the root for the current OS, or default if none is set."""
    set_os(os_name)
    assert (
        unameit_config.build_path("project_root", {"project": "MYPUPPIES"}) == expected
    )


def test_unameit_build_path_payload_overrides_os_root(unameit_config: UNameIt, set_os):
    """Test payload root takes precedence over the OS-specific root."""
    set_os("windows")
    result = unameit_config.build_path(
        "project_root", {"root": "/shows", "project": "MYPUPPIES"}
    )
    assert result == "/shows/MYPUPPIES"


@pytest.mark.parametrize(
    ("root", "expected"),
    [
        ("P:", "P:/MYPUPPIES"),
        ("P:/", "P:/MYPUPPIES"),
        ("P://", "P:/MYPUPPIES"),
        ("//server/share", "//server/share/MYPUPPIES"),
        ("", "/MYPUPPIES"),
        ("/", "/MYPUPPIES"),
    ],
)
def test_unameit_build_path_os_root_slashes(
    unameit_config: UNameIt, set_os, root: str, expected: str
):
    """Test extra slashes at the root/template boundary are removed, UNC kept."""
    set_os("windows")
    unameit_config._tokens.root.os.windows = root
    assert (
        unameit_config.build_path("project_root", {"project": "MYPUPPIES"}) == expected
    )


def test_unameit_build_path_null_os_value_falls_back_to_default(
    unameit_config: UNameIt, set_os
):
    """Test a null OS value is treated as unset and falls back to default."""
    set_os("linux")
    unameit_config._tokens.root.os.linux = None
    assert unameit_config.build_path("project_root", {"project": "MYPUPPIES"}) == (
        "/projects/MYPUPPIES"
    )


def test_unameit_extract_path_windows_root(unameit_config: UNameIt, set_os):
    """Test extract_path() matches the root for the current OS (windows)."""
    set_os("windows")
    assert unameit_config.extract_path("project_root", "P:/MYPUPPIES") == {
        "root": "P:",
        "project": "MYPUPPIES",
    }


def test_unameit_extract_path_other_os_root_not_matched(unameit_config: UNameIt):
    """Test extract_path() only matches the current OS root (linux here)."""
    assert unameit_config.extract_path("project_root", "P:/MYPUPPIES") == {}


def test_unameit_extract_path_empty_os_root(unameit_config: UNameIt, set_os):
    """Test extract_path() matches an empty root."""
    set_os("linux")
    unameit_config._tokens.root.os.linux = ""
    assert unameit_config.extract_path("project_root", "/MYPUPPIES") == {
        "root": "",
        "project": "MYPUPPIES",
    }


@pytest.mark.parametrize("os_name", ["linux", "macos", "windows"])
def test_unameit_build_extract_round_trip(
    unameit_config: UNameIt, set_os, os_name: str
):
    """Test extracting a built path and building again gives the same path."""
    set_os(os_name)
    path = unameit_config.build_path("project_root", {"project": "MYPUPPIES"})
    data = unameit_config.extract_path("project_root", path)
    assert unameit_config.build_path("project_root", data) == path


def _set_tokens(unameit_obj: UNameIt, tokens: dict) -> None:
    """Replace the loaded config with one using the given tokens section."""
    unameit_obj._conf = OmegaConf.create(
        {"tokens": tokens, "templates": {"project_root": "@{root}/@{project}"}}
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
