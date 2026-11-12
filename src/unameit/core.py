"""Core library of UNameIt."""

import re
from pathlib import Path
from typing import Any

from omegaconf import DictConfig, ListConfig, OmegaConf

from unameit.log import Logger
from unameit.util import (
    OS_KEYS,
    current_os,
    find_tokens_from_template,
    strip_boundary_slashes,
    substitute_token,
)

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

        self._validate_os_mappings()

    def _validate_os_mappings(self) -> None:
        """Validate each token, and the `os` mapping of tokens that define one.

        Raises:
            ValueError: If a token isn't a mapping, `os` isn't a mapping, an OS key is
                unknown, or an OS value isn't a string.
        """
        for name, token in (self._conf.tokens or {}).items():
            if not isinstance(token, DictConfig):
                raise TypeError(f"Token '{name}' must be a mapping")
            if "os" not in token:
                continue

            os_values = token.get("os")
            if not isinstance(os_values, DictConfig):
                raise TypeError(f"'os' of token '{name}' must be a mapping")
            for os_name, value in os_values.items():
                if os_name not in OS_KEYS:
                    raise ValueError(
                        f"Unknown OS '{os_name}' in token '{name}', "
                        f"expected one of: {', '.join(sorted(OS_KEYS))}"
                    )
                if value is not None and not isinstance(value, str):
                    raise ValueError(
                        f"Value for OS '{os_name}' in token '{name}' must be a string"
                    )

    def _resolve_default(self, token: str) -> str | None:
        """Resolve the default value of a token for the current OS.

        The `os` entry for the current OS wins if it is set (an empty string is a valid,
        explicit value). Otherwise `default` is used.

        Args:
            token (str): Token name to resolve.

        Returns:
            str | None: Resolved value, or None if the token has no value for this OS.
        """
        token_conf = self._tokens.get(token)
        if token_conf is None:
            return None

        os_values = token_conf.get("os")
        if os_values is not None:
            value = os_values.get(current_os())
            if value is not None:
                return str(value)

        value = token_conf.get("default")
        return None if value is None else str(value)

    def _replace_tokens_with_defaults(
        self, template: str, tokens: list[str], payload: dict[str, Any]
    ) -> str:
        """Replace collected tokens with default values for the current OS.

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
            default = self._resolve_default(token)
            if default is not None:
                result = substitute_token(result, token, default)
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
                result = substitute_token(result, token, str(payload[token]))
        return result

    def _build_search_pattern_from_template(self, template: str) -> str:
        """Build search pattern from template string.

        Literal parts are escaped and matched verbatim. Path roots (tokens defining `os`)
        match their literal value for the current OS, with slashes normalized the same way
        as in build_path(). Other tokens become named groups using the pattern set in the
        config (matched one or more times), falling back to any non-empty path segment
        when the token defines no pattern.

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
                search_pattern += self._token_group(token, template, match)
            pos = match.end()
        search_pattern += re.escape(template[pos:])
        return search_pattern

    def _token_group(self, token: str, template: str, match: re.Match[str]) -> str:
        """Return the named group regex for one occurrence of a token in a template.

        Args:
            token (str): Token name.
            template (str): Template the occurrence belongs to.
            match (re.Match[str]): Match of the `$token` occurrence in template.

        Returns:
            str: Named group regex for the token.
        """
        token_conf = self._tokens.get(token)
        if token_conf is not None and "os" in token_conf:
            root = self._resolve_default(token)
            if root is not None:
                has_lead = match.start() > 0 and template[match.start() - 1] == "/"
                has_trail = template[match.end() : match.end() + 1] == "/"
                literal = strip_boundary_slashes(root, has_lead, has_trail)
                return f"(?P<{token}>{re.escape(literal)})"
        if token_conf is not None and "pattern" in token_conf:
            return f"(?P<{token}>(?:{token_conf.pattern})+)"
        return f"(?P<{token}>[^/]+)"

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
        Tokens that define `os` are path roots: they match their value for the current OS
        (falling back to `default`). For example, on Linux with the `$root/$project` template
        and root default `/projects`, `/projects/superdude` returns
        `{"root": "/projects", "project": "superdude"}`.

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

        search_pattern = self._build_search_pattern_from_template(template)
        logger.debug("Extract pattern: %s", search_pattern)

        # Match the built pattern against the whole path and collect the named groups.
        matched = re.fullmatch(search_pattern, path)
        if matched:
            result = matched.groupdict()

        return result
