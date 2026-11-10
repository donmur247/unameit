"""Test suite for UNameIt core library."""

from pathlib import Path

import pytest
from omegaconf import OmegaConf

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
