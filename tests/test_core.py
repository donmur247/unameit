"""Test suite for UNameIt core library."""

from pathlib import Path

import pytest

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
