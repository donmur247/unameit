"""Core library of UNameIt."""

import re
from pathlib import Path
from typing import Any

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
        self._config_file: Path = Path()

        # Init to empty config
        self._conf = OmegaConf.create()
        self._tokens: DictConfig = OmegaConf.create()
        self._templates: DictConfig = OmegaConf.create()

    @property
    def config_dir(self) -> str:
        """Property to return configuration dir.

        Returns:
            str: Full path of configuration directory.
        """
        return self._config_dir.as_posix()

    @property
    def config_file(self) -> str:
        """Property to return configuration file.

        Returns:
            str: Full path of configuration file.
        """
        return self._config_file.as_posix()

    @property
    def conf(self) -> DictConfig | ListConfig:
        """Property to return dict or list config.

        Returns:
            DictConfig: DictConfig or ListConfig object.
        """
        return self._conf

    def _validate(self) -> None:
        """Validate the config after loading."""
        if not self._conf:
            raise ValueError("No config loaded")

        sections = self._conf.keys()
        if "templates" not in sections:
            raise ValueError("No templates section in config")

        if "tokens" not in sections:
            raise ValueError("No tokens section in config")

    def load(self, config_file: str) -> None:
        """Load config from provided config file.

        Args:
            config_file (str): Configuration file.
        """
        self._config_file = self._config_dir / config_file
        self._conf = OmegaConf.load(self.config_file)
        self._validate()
        self._tokens = self._conf.tokens
        self._templates = self._conf.templates

    def build_path(self, template_name: str, payload: dict[str, Any]) -> str | None:
        """Build path from selected template and payload data.

        Args:
            template_name (str): Template name to use.
            payload (dict[str, Any]): Data to use for template substitution.

        Returns:
            str | None: Full path of built template, or None if template not found.
        """
        template = self._templates.get(template_name)
        if not template:
            return None

        # Get tokens from template. Tokens are started with `$`. For example
        # `$root/$project/some/path/$filename.$ext` yields root, project, filename, ext.
        # Longer tokens are substituted first to avoid prefix collisions (e.g. `$root`
        # clobbering `$root_dir`).
        tokens = sorted(set(re.findall(r"\$([\w]+)", template)), key=len, reverse=True)

        result = template

        # First pass: replace each token with corresponding default value found from
        # self._tokens. Tokens provided by payload are skipped here, as payload values
        # take precedence over defaults.
        for token in tokens:
            if token in payload:
                continue
            token_conf = self._tokens.get(token)
            if token_conf is not None and "default" in token_conf:
                result = result.replace(f"${token}", str(token_conf.default))

        # Second pass: replace tokens with matching values from payload.
        for token in tokens:
            if token in payload:
                result = result.replace(f"${token}", str(payload[token]))

        return result
