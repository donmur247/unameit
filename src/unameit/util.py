"""Utility functions for unameit."""

import re
import sys

# Maps sys.platform values to the keys accepted under a token's `os` mapping.
OS_NAMES = {"win32": "windows", "linux": "linux", "darwin": "macos"}
OS_KEYS = frozenset(OS_NAMES.values())


def find_tokens_from_template(template: str) -> list[str]:
    """Find tokens from provided template.

    Tokens are started with `$`. For example
    `$root/$project/some/path/$filename.$ext` yields root, project, filename, ext.
    Longer tokens are substituted first to avoid prefix collisions (e.g. `$root`
    clobbering `$root_dir`).

    Args:
        template (str): Description.

    Returns:
        list[str]: Description.
    """
    pattern = r"\$([\w]+)"
    return sorted(set(re.findall(pattern, template)), key=len, reverse=True)


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


def substitute_token(text: str, token: str, value: str) -> str:
    """Replace every `$token` in text with value, without doubling slashes.

    Only whole token names are matched, so `$root` doesn't match inside `$root_dir`.

    Args:
        text (str): Text containing tokens.
        token (str): Token name to replace (without `$`).
        value (str): Value to substitute.

    Returns:
        str: Text with the token replaced.
    """

    def replace(match: re.Match[str]) -> str:
        name, trail = match.group(1), match.group(2)
        if name != token:
            return match.group(0)
        has_lead = match.start() > 0 and text[match.start() - 1] == "/"
        return strip_boundary_slashes(value, has_lead, bool(trail)) + trail

    return re.sub(r"\$(\w+)(/?)", replace, text)
