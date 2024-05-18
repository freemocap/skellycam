import logging
import multiprocessing

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.cameras.config.camera_config import CameraConfig

logger = logging.getLogger(__name__)


class SingleCameraTriggers(BaseModel):
    camera_id: CameraId
    initial_trigger: multiprocessing.Event
    grab_frame_trigger: multiprocessing.Event
    frame_grabbed_trigger: multiprocessing.Event
    retrieve_frame_trigger: multiprocessing.Event
    camera_ready_event: multiprocessing.Event

    @classmethod
    def from_camera_config(cls, camera_config: CameraConfig):
        return cls(
            camera_id=CameraId(camera_config.camera_id),
            camera_ready_event=multiprocessing.Event(),
            initial_trigger=multiprocessing.Event(),
            grab_frame_trigger=multiprocessing.Event(),
            frame_grabbed_trigger=multiprocessing.Event(),
            retrieve_frame_trigger=multiprocessing.Event(),
        )


