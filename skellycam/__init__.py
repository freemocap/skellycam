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

# from skellycam.api.routers import SKELLYCAM_ROUTERS
# from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
# from skellycam.core.shared_memory.multi_frame_payload_ring_buffer import \
#     MultiFrameSharedMemoryRingBuffer
# from skellycam.core.types.type_overloads import CameraIndex, CameraName
# from skellycam.skellycam_app.skellycam_app import SkellycamApplication
# from skellycam.skellycam_app.skellycam_app_ipc.ipc_manager import InterProcessCommunicationManager
# from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import create_websocket_log_queue
from skellycam.system.logging_configuration.configure_logging import configure_logging
from skellycam.system.logging_configuration.log_levels import LogLevels

LOG_LEVEL = LogLevels.LOOP
configure_logging(LOG_LEVEL)


__all__ = [
    "__author__",
    "__email__",
    "__version__",
    "__description__",
    "__package_name__",
    "__repo_url__",
    "__repo_issues_url__",
    "__pypi_url__",
    # 'SKELLYCAM_ROUTERS',
    # 'SkellycamApplication',
    # 'MultiFrameSharedMemoryRingBuffer',
    # 'CameraConfig',
    # 'InterProcessCommunicationManager',
    'LOG_LEVEL'
]