"""Utility functions for unameit."""

import re
import sys
from collections.abc import Mapping

# A token is written as `@{name}`. The braces delimit the name, so a token can be followed
# directly by literal text, e.g. `@{task}_@{task_description}` or `@{shot}_01`. OmegaConf's
# `${...}` interpolation is never treated as a token.
TOKEN_PATTERN = re.compile(r"@\{(\w+)\}")
# Same as TOKEN_PATTERN, but also captures a `/` directly after the token.
_TOKEN_WITH_TRAIL_PATTERN = re.compile(r"@\{(\w+)\}(/?)")

# Maps sys.platform values to the keys accepted under a token's `os` mapping.
OS_NAMES = {"win32": "windows", "linux": "linux", "darwin": "macos"}
OS_KEYS = frozenset(OS_NAMES.values())


def find_tokens_from_template(template: str) -> list[str]:
    """Find tokens from provided template.

    Tokens are written as `@{name}`. For example
    `@{root}/@{project}/some/path/@{filename}.@{ext}` yields root, project, filename, ext.
    Tokens are returned longest first.

    Args:
        template (str): Description.

    Returns:
        list[str]: Description.
    """
    return sorted(set(TOKEN_PATTERN.findall(template)), key=len, reverse=True)


def current_os() -> str:
    """Return the current OS name, used to pick a token's `os` entry.

    Returns:
        str: `windows`, `linux`, `macos`, or the raw `sys.platform` value for other OSes.
    """
    return OS_NAMES.get(sys.platform, sys.platform)


def strip_boundary_slashes(value: str, has_lead: bool, has_trail: bool) -> str:
    """Remove slashes from a value that would double up with slashes in the template.

    Args:
        value (str): Value to substitute into the template.
        has_lead (bool): Whether the template has a `/` directly before the token.
        has_trail (bool): Whether the template has a `/` directly after the token.

    Returns:
        str: Value without the leading/trailing slashes the template already provides.
    """
    if has_lead:
        value = value.lstrip("/")
    if has_trail:
        value = value.rstrip("/")
    return value


def substitute_tokens(text: str, values: Mapping[str, str]) -> str:
    """Replace each token in text that has a value, in one pass, without doubling slashes.

    The text is scanned once, so substituted values are never scanned for tokens again.
    Names are delimited by braces, so `@{root}` never matches part of `@{root_dir}`.

    Args:
        text (str): Text containing tokens.
        values (Mapping[str, str]): Token name to value. Tokens missing from it are left as is.

    Returns:
        str: Text with the tokens replaced.
    """

    def replace(match: re.Match[str]) -> str:
        name, trail = match.group(1), match.group(2)
        if name not in values:
            return match.group(0)
        has_lead = match.start() > 0 and text[match.start() - 1] == "/"
        return strip_boundary_slashes(values[name], has_lead, bool(trail)) + trail

    return _TOKEN_WITH_TRAIL_PATTERN.sub(replace, text)


def substitute_token(text: str, token: str, value: str) -> str:
    """Replace every `@{token}` in text with value, without doubling slashes.

    Args:
        text (str): Text containing tokens.
        token (str): Token name to replace (without `@{}`).
        value (str): Value to substitute.

    Returns:
        str: Text with the token replaced.
    """
    return substitute_tokens(text, {token: value})
