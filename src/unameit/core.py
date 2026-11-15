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

    def _build_search_pattern_from_template(
        self, template: str, end: int | None = None
    ) -> str:
        """Build search pattern from template string.

        Literal parts are escaped and matched verbatim. Path roots (tokens defining `os`)
        match their literal value for the current OS, with slashes normalized the same way
        as in build_path(). Other tokens become named groups using the pattern set in the
        config (matched one or more times), falling back to any non-empty path segment
        when the token defines no pattern.

        Args:
            template (str): Template string to build pattern from.
            end (int | None): Position in template to stop at (exclusive). Defaults to the
                whole template.

        Returns:
            str: Search pattern string.
        """
        end = len(template) if end is None else end
        search_pattern = ""
        seen = set()
        pos = 0
        for match in re.finditer(r"\$(\w+)", template):
            if match.start() >= end:
                break
            search_pattern += re.escape(template[pos : match.start()])
            token = match.group(1)
            if token in seen:
                # Repeated token: use a back reference so it must match the same value.
                search_pattern += f"(?P={token})"
            else:
                seen.add(token)
                search_pattern += self._token_group(token, template, match)
            pos = match.end()
        search_pattern += re.escape(template[pos:end])
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

    def _get_template(self, template_name: str) -> str | None:
        """Return the template string for a template name.

        Dots select nested templates, e.g. `assets.root`, and interpolations are resolved.

        Args:
            template_name (str): Template name to look up.

        Returns:
            str | None: The template string, or None if the name is empty, not found, or
                doesn't refer to a string template.
        """
        if not template_name:
            return None
        template = OmegaConf.select(self._templates, template_name)
        return template if isinstance(template, str) else None

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
            template_name (str): Template name to use. Dots select nested templates, e.g.
                `assets.root`.
            payload (dict[str, Any]): Data to use for template substitution.

        Returns:
            str | None: Full path of built template, or None if template not found.
        """
        template = self._get_template(template_name)
        if not template:
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

    def extract_path(
        self, template_name: str, path: str, exact: bool = True
    ) -> dict[str, Any]:
        """Extract tokens from an input path and return a dictionary with matching tokens and values.

        Tokens are extracted from the path using the template tokens defined in the config.
        Tokens that define `os` are path roots: they match their value for the current OS
        (falling back to `default`). For example, on Linux with the `$root/$project` template
        and root default `/projects`, `/projects/superdude` returns
        `{"root": "/projects", "project": "superdude"}`.

        Args:
            template_name (str): The name of the template to use for extracting tokens.
                Dots select nested templates, e.g. `assets.root`.
            path (str): The input path to unpack.
            exact (bool, optional): If True, the whole path must match the template. If False,
                the longest leading part of the template that matches the path is extracted.
                Path elements left over, or from the first mismatch onward, are returned as a
                list of strings under `not_matched`. Defaults to True.

        Returns:
            dict[str, Any]: A dictionary mapping tokens to their unpacked values.
                Empty dictionary if the template is not found, or if `exact` is True and the
                path doesn't match the template. When `exact` is False, the dictionary always
                has a `not_matched` key.
        """
        search_pattern: str = ""
        result: dict[str, Any] = {}
        template = self._get_template(template_name)
        if not template:
            return result

        if exact:
            search_pattern = self._build_search_pattern_from_template(template)
            logger.debug("Extract pattern: %s", search_pattern)

            # Match the built pattern against the whole path and collect the named groups.
            matched = re.fullmatch(search_pattern, path)
            if matched:
                result = matched.groupdict()
            return result

        # Try the longest template prefix first. Prefixes end at a template "/" separator (or at
        # the end of the template), and the match must be followed by "/" or the end of the path,
        # so a token never matches part of a path element.
        cuts = [i for i, char in enumerate(template) if char == "/" and i > 0]
        cuts.append(len(template))
        matched: re.Match[str] | None = None
        for cut in reversed(cuts):
            search_pattern = self._build_search_pattern_from_template(template, cut)
            matched = re.match(search_pattern + r"(?=/|\Z)", path)
            if matched:
                break
        logger.debug("Extract pattern: %s", search_pattern)

        remainder = path
        if matched:
            result = matched.groupdict()
            remainder = path[matched.end() :]
        result["not_matched"] = [part for part in remainder.split("/") if part]
        return result
