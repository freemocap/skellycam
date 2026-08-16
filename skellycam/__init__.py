
"""Top-level package for skellycam."""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2.0.0-alpha.6"

__description__ = "A simple python API for efficiently connecting to and recording synchronized videos from one or multiple cameras 💀📸"
__package_name__ = "skellycam"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}"
__repo_issues_url__ = f"{__repo_url__}/issues"
__pypi_url__ = f"https://pypi.org/project/{__package_name__}"

__package_root__ = str(__import__("pathlib").Path(__file__).parent)

from beartype.claw import beartype_this_package
beartype_this_package()

import multiprocessing


multiprocessing.freeze_support()

from skellylogs import LogLevels


LOG_LEVEL = LogLevels.TRACE



__all__ = [
    "__author__",
    "__email__",
    "__version__",
    "__description__",
    "__package_name__",
    "__repo_url__",
    "__repo_issues_url__",
    "__pypi_url__",
]
