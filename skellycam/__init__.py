"""Top-level package for skellycam."""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2023.09.1086"

__description__ = "A simple python API for efficiently connecting to and recording synchronized videos from one or multiple cameras 💀📸"
__package_name__ = "skellycam"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"

from skellycam.system.environment.configure_logging import configure_logging, LogLevel

configure_logging(LogLevel.TRACE)

