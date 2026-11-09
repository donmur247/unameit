"""Core library of UNameIt."""

from pathlib import Path

from omegaconf import DictConfig, ListConfig, OmegaConf


class UNameIt:
    """Core class definition of UNameIt."""

    def __init__(self, config_dir: str) -> None:
        """Constructor method."""
        self._config_dir: Path = Path(config_dir)
        if not self._config_dir.exists() or not self._config_dir.is_dir():
            raise OSError(
                f"Configuration dir '{self._config_dir.as_posix()}' doesn't exist or not a directory"
            )

        # Init to empty config
        self._conf = OmegaConf.create()

    def load(self, config_file: str) -> None:
        """Load config from provided config file.

        Args:
            config_file (str): Configuration file.
        """
        config_path = self._config_dir / config_file
        self._conf = OmegaConf.load(config_path.as_posix())

    @property
    def config_dir(self) -> str:
        """Property to return configuration dir.

        Returns:
            str: Full path of configuration directory.
        """
        return self._config_dir.as_posix()

    @property
    def conf(self) -> DictConfig | ListConfig:
        """Property to return dict or list config.

        Returns:
            DictConfig: DictConfig or ListConfig object.
        """
        return self._conf
