"""Top-level package for skellycam."""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2023.09.1086"

__description__ = "A simple python API for efficiently connecting to and recording synchronized videos from one or multiple cameras 💀📸"
__package_name__ = "skellycam"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}"
__repo_issues_url__ = f"{__repo_url__}/issues"
__pypi_url__ = f"https://pypi.org/project/{__package_name__}"

__package_root__ = __file__.replace("/__init__.py", "")

from skellycam.api.routers import SKELLYCAM_ROUTERS
from skellycam.core import CameraId
from skellycam.gui.qt.widgets.camera_widgets.camera_panel import SkellycamCameraPanel
from skellycam.gui.qt.widgets.side_panel_widgets.camera_control_panel import SkellycamCameraControlPanel
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import create_skellycam_app_controller
from skellycam.system.logging_configuration.configure_logging import configure_logging
from skellycam.system.logging_configuration.logger_builder import LogLevels

configure_logging(LogLevels.TRACE)


__all__ = [
    "__author__",
    "__email__",
    "__version__",
    "__description__",
    "__package_name__",
    "__repo_url__",
    "__repo_issues_url__",
    "__pypi_url__",
    'SkellycamCameraPanel',
    'SkellycamCameraControlPanel',
    'create_skellycam_app_controller',
    'SKELLYCAM_ROUTERS',
    'CameraId',
]