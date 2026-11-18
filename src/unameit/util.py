"""Utility functions for unameit."""

import re
import sys
from collections.abc import Container, Mapping

# A token is written as `@{name}`. The braces delimit the name, so a token can be followed
# directly by literal text, e.g. `@{task}_@{task_description}` or `@{shot}_01`. OmegaConf's
# `${...}` interpolation is never treated as a token.
TOKEN_PATTERN = re.compile(r"@\{(\w+)\}")
# Same as TOKEN_PATTERN, but also captures a `/` directly after the token.
_TOKEN_WITH_TRAIL_PATTERN = re.compile(r"@\{(\w+)\}(/?)")

# Optional part of a template, e.g. `[.@{udim}.]`. A group is optional only when it contains a
# token, so other brackets are literal text. Brackets can't be nested.
OPTIONAL_GROUP_PATTERN = re.compile(r"\[([^\[\]]*)\]")
# Same as OPTIONAL_GROUP_PATTERN, but also captures a `/` directly after the group.
_OPTIONAL_GROUP_WITH_SLASH_PATTERN = re.compile(r"\[([^\[\]]*)\](/?)")

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


def resolve_optional_groups(text: str, available: Container[str]) -> str:
    """Keep or drop each optional group in text, depending on the tokens it contains.

    A group is optional when it contains a token. It is kept, without its brackets, when every
    token in it is available, and removed otherwise. When a removed group sits between two
    slashes, one slash is removed with it, so `@{root}/[@{shot}]/@{name}` becomes
    `@{root}/@{name}`.

    Args:
        text (str): Text that may contain optional groups.
        available (Container[str]): Names of the tokens that have a value.

    Returns:
        str: Text with the optional groups resolved. Tokens themselves are left as they are.
    """

    def replace(match: re.Match[str]) -> str:
        content, slash = match.group(1), match.group(2)
        names = TOKEN_PATTERN.findall(content)
        if not names:
            return match.group(0)
        if all(name in available for name in names):
            return content + slash
        between_slashes = match.start() > 0 and text[match.start() - 1] == "/"
        return "" if between_slashes else slash

    return _OPTIONAL_GROUP_WITH_SLASH_PATTERN.sub(replace, text)
