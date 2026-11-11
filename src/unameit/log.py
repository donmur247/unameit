"""Logging module for the unameit package."""

import logging


class TerminalHandler(logging.StreamHandler):
    """Custom terminal handler class for unameit."""

    def __init__(self, level: int = logging.INFO) -> None:
        """Constructor method."""
        super().__init__()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.setFormatter(formatter)
        self.setLevel(level)


class Logger(logging.Logger):
    """Custom logger class for unameit."""

    def __init__(self, name: str) -> None:
        """Constructor method."""
        super().__init__(name)
        self.setLevel(logging.INFO)
        self.propagate = False
        self.addHandler(TerminalHandler())


__all__ = ["Logger"]
