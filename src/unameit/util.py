"""Utility functions for unameit."""

import re


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
