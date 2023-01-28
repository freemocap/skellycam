"""Top-level package for skellycam."""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2023.01.1052"
__description__ = "A simple python API for efficiently watching camera streams 💀📸"
__package_name__ = "skellycam"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"


import sys
from pathlib import Path


print(f"This is printing from {__file__}")

base_package_path = Path(__file__).parent
print(f"adding base_package_path: {base_package_path} : to sys.path")
sys.path.insert(0, str(base_package_path))  # add parent directory to sys.path

from skellycam.system.environment.default_paths import get_log_file_path
from skellycam.system.log_config.logsetup import configure_logging

configure_logging(log_file_path=get_log_file_path())

from skellycam.opencv.camera.camera import Camera
from skellycam.opencv.camera.models.camera_config import CameraConfig


from skellycam.qt_gui.widgets.skelly_cam_config_parameter_tree_widget import SkellyCamParameterTreeWidget
from skellycam.qt_gui.widgets.skelly_cam_controller_widget import SkellyCamControllerWidget
from skellycam.qt_gui.widgets.skelly_cam_viewer_widget import SkellyCamViewerWidget
from skellycam.qt_gui.widgets.skelly_cam_directory_view_widget import SkellyCamDirectoryViewWidget

