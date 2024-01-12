from typing import Dict

from skellycam.backend.models.cameras.camera_config import CameraConfig
from skellycam.backend.models.cameras.camera_id import CameraId

CameraConfigs = Dict[CameraId, CameraConfig]
