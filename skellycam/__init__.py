"""Top-level package for skellycam."""

__author__ = """Skelly FreeMoCap"""
__email__ = 'info@freemocap.org'
__version__ = '0.1.0'

from skellycam.opencv.camera.camera import Camera
from skellycam.opencv.camera.models.camera_config import CameraConfig
from skellycam.system.log_config.logsetup import configure_logging

configure_logging()
