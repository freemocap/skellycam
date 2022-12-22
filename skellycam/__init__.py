"""Top-level package for skellycam."""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2022.12.1013"
__description__ = "A simple python API for efficiently watching camera streams 💀📸"

import logging
import sys
from pathlib import Path

print(f"This is printing from {__file__}")

base_package_path = Path(__file__).parent
print(f"adding base_package_path: {base_package_path} : to sys.path")
sys.path.insert(0, str(base_package_path))  # add parent directory to sys.path

from skellycam.opencv.camera.camera import Camera
from skellycam.opencv.camera.models.camera_config import CameraConfig
from skellycam.system.log_config.logsetup import configure_logging

logger = logging.getLogger(__name__)

configure_logging()
