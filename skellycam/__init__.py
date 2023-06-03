"""Top-level package for skellycam."""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2023.03.1079"

__description__ = "A simple python API for efficiently watching camera streams 💀📸"
__package_name__ = "skellycam"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"


from skellycam.opencv.camera.camera import Camera
from skellycam.opencv.camera.config.camera_config import CameraConfig

from skellycam.gui.qt.widgets.skelly_cam_config_parameter_tree_widget import (
    SkellyCamParameterTreeWidget,
)
from skellycam.gui.qt.widgets.skelly_cam_controller_widget import (
    SkellyCamControllerWidget,
)
from skellycam.gui.qt.skelly_cam_widget import SkellyCamWidget
from skellycam.gui.qt.widgets.skelly_cam_directory_view_widget import (
    SkellyCamDirectoryViewWidget,
)
