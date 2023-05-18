import logging
from typing import Dict, List, Optional

from skellycam.detection.detect_cameras import detect_cameras
from skellycam.opencv.camera.types.camera_id import CameraId
from skellycam import CameraConfig

logger = logging.getLogger(__name__)

class CameraConfigManager:
    """
    A class to manage camera configurations.
    """

    def __init__(self, camera_ids_list: Optional[List[CameraId]] = None,
                 camera_config_dictionary: Optional[Dict[CameraId, CameraConfig]] = None):
        """
        Initialize the CameraConfigurationManager.

        Args:
            camera_ids_list (Optional[List[CameraId]]): List of camera ids. If None, will get ids from camera_config_dictionary
                or detect cameras if the dictionary is also None. Default is None.
            camera_config_dictionary (Optional[Dict[CameraId, CameraConfig]]): A dictionary mapping camera ids to their configuration.
                If None, will create a default configuration for each camera id. Default is None.
        """
        if camera_config_dictionary is not None:
            self._camera_ids = list(camera_config_dictionary.keys())
        elif camera_ids_list is not None:
            self._camera_ids = camera_ids_list
        else:
            self._camera_ids = detect_cameras().cameras_found_list

        if camera_config_dictionary is None:
            logger.info(f"No camera config dict passed in, using default config: {CameraConfig()}")
            self._camera_config_dictionary = {}
            for camera_id in self._camera_ids:
                self._camera_config_dictionary[camera_id] = CameraConfig(camera_id=camera_id)
        else:
            self._camera_config_dictionary = camera_config_dictionary

    @property
    def camera_config_dictionary(self) -> Dict[CameraId, CameraConfig]:
        """
        Property to get the camera configuration dictionary.

        Returns:
            Dict[CameraId, CameraConfig]: The current camera configuration dictionary.
        """
        return self._camera_config_dictionary

    def update_camera_configs(self, camera_config_dictionary: Dict[CameraId, CameraConfig]):
        """
        Update the camera configurations with a new dictionary.

        Args:
            camera_config_dictionary (Dict[CameraId, CameraConfig]): The new camera configuration dictionary.
        """
        logger.info(f"Updating camera configs to {camera_config_dictionary}")
        self._camera_config_dictionary = camera_config_dictionary
