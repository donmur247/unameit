"""Core library of UNameIt."""

import re
from pathlib import Path
from typing import Any

from omegaconf import DictConfig, ListConfig, OmegaConf

from unameit.log import Logger
from unameit.util import find_tokens_from_template

logger = Logger(__name__)


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

        logger.info(
            "UNameIt initialized using config dir '%s'", self._config_dir.as_posix()
        )

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

    def _replace_tokens_with_defaults(
        self, template: str, tokens: list[str], payload: dict[str, Any]
    ) -> str:
        """Replace collected tokens with default values for each token match in config.
        Tokens provided by payload are skipped here, as payload values
        take precedence over defaults.

        Args:
            template (str): Template string to replace tokens in.
            tokens (list[str]): List of tokens to replace in template.
            payload (dict[str, Any]): Dictionary of token values to replace with.

        Returns:
            str: Template string with tokens replaced by default values.
        """
        result = template
        for token in tokens:
            if token in payload:
                continue
            token_conf = self._tokens.get(token)
            if token_conf is not None and "default" in token_conf:
                result = result.replace(f"${token}", str(token_conf.default))
        return result

    def _replace_tokens_with_payload(
        self, template: str, tokens: list[str], payload: dict[str, Any]
    ) -> str:
        """Replace tokens in template with values from payload.

        Args:
            template (str): Template string to replace tokens in.
            tokens (list[str]): List of tokens to replace.
            payload (dict[str, Any]): Dictionary of token values to replace with.

        Returns:
            str: Template string with tokens replaced by payload values.
        """
        result = template
        for token in tokens:
            if token in payload:
                result = result.replace(f"${token}", str(payload[token]))
        return result

    def _build_search_pattern_from_template(self, template: str) -> str:
        """Build search pattern from template string.

        Literal parts are escaped and matched verbatim, while each token
        becomes a named group using the pattern set in the config
        (matched one or more times), falling back to any non-empty path
        segment when the token defines no pattern.

        Args:
            template (str): Template string to build pattern from.

        Returns:
            str: Search pattern string.
        """
        search_pattern = ""
        seen = set()
        pos = 0
        for match in re.finditer(r"\$(\w+)", template):
            search_pattern += re.escape(template[pos : match.start()])
            token = match.group(1)
            if token in seen:
                # Repeated token: use a back reference so it must match the same value.
                search_pattern += f"(?P={token})"
            else:
                seen.add(token)
                token_conf = self._tokens.get(token)
                if token_conf is not None and "pattern" in token_conf:
                    search_pattern += f"(?P<{token}>(?:{token_conf.pattern})+)"
                else:
                    search_pattern += f"(?P<{token}>[^/]+)"
            pos = match.end()
        search_pattern += re.escape(template[pos:])
        return search_pattern

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

        logger.info("Config loaded from '%s'", self._config_file.as_posix())

    def build_path(self, template_name: str, payload: dict[str, Any]) -> str | None:
        """Build path from selected template and payload data.

        Args:
            template_name (str): Template name to use.
            payload (dict[str, Any]): Data to use for template substitution.

        Returns:
            str | None: Full path of built template, or None if template not found.
        """
        template = self._templates.get(template_name)
        if not template or not isinstance(template, str):
            return None

        tokens = find_tokens_from_template(template)
        if not tokens:
            return None
        logger.debug("Build tokens: %s", tokens)

        result = self._replace_tokens_with_defaults(template, tokens, payload)
        logger.debug("Build first pass result: %s", result)

        result = self._replace_tokens_with_payload(result, tokens, payload)
        logger.debug("Build second pass result: %s", result)

        return result

    def extract_path(self, template_name: str, path: str) -> dict[str, Any]:
        """Extract tokens from an input path and return a dictionary with matching tokens and values.
        Tokens are extracted from the path using the template tokens defined in the config.
        For example `/project/superdude` where the template name used is `$root/$project`
        returns `{"root": "project", "project": "superdude"}`.

        Args:
            template_name (str): The name of the template to use for extracting tokens.
            path (str): The input path to unpack.

        Returns:
            dict[str, Any]: A dictionary mapping tokens to their unpacked values.
                Empty dictionary if the template is not found or the path doesn't match
                the template.
        """
        result: dict[str, Any] = {}
        template = self._templates.get(template_name)
        if not template:
            return result

        # Token values may carry their own leading slash (e.g. a default of `/projects`),
        # so align the path with the template structure before matching.
        if not template.startswith("/"):
            path = path.removeprefix("/")

        search_pattern = self._build_search_pattern_from_template(template)
        logger.debug("Extract pattern: %s", search_pattern)

        # Match the built pattern against the whole path and collect the named groups.
        matched = re.fullmatch(search_pattern, path)
        if matched:
            result = matched.groupdict()

        return result
