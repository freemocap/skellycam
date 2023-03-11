import logging
import time
from typing import List

from pydantic import BaseModel

from skellycam.utilities.timeout.timeout import Timeout

logger = logging.getLogger(__name__)

CAMERA_START_SYNCHRONIZE_IN_SECONDS = 10


class WaitArgs(BaseModel):
    camera_ids: List[str]


class StartSynchronizer:
    def __init__(self, strategy):
        self._strategy = strategy

    def wait_for_cameras_to_start(self, args: WaitArgs):
        logger.info(f"Waiting for cameras {args.camera_ids} to start")
        all_cameras_started = False
        with Timeout(CAMERA_START_SYNCHRONIZE_IN_SECONDS) as tm:
            while not all_cameras_started and not tm.is_timed_out():
                time.sleep(0.5)
                has_started = dict.fromkeys(args.camera_ids, False)

                for camera_id in args.camera_ids:
                    has_started[camera_id] = self._check_if_camera_is_ready(camera_id)

                all_cameras_started = all(list(has_started.values()))
            return True

        return False

    def _check_if_camera_is_ready(self, cam_id: str):
        return self._strategy.check_if_camera_is_ready(cam_id)
