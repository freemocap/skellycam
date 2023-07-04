import logging
import multiprocessing
import traceback
from multiprocessing import Process
from time import sleep
from typing import Any, Dict, List, Union

from setproctitle import setproctitle

from skellycam import Camera, CameraConfig
from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class InternalCaptureQueueProcess(Process):
    def run(self):
        self._start_capture(*self._args)

    def _start_capture(
            self,
            camera_ids: List[str],
            frame_queues_by_camera: Dict[str, multiprocessing.Queue],
            cam_ready_ipc: Dict[str, bool],
            stop_event: multiprocessing.Event,
    ):
        logger.info(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_ids}"
        )

        logger.info(f"Setting process title to {self.name}")
        setproctitle(self.name)

        cameras_by_id = self._create_cameras(camera_ids)

        for camera_id, camera in cameras_by_id.items():
            camera.connect()
            cam_ready_ipc[camera_id] = True

        try:
            while not stop_event.is_set():
                sleep(0.01)
                for camera_id, camera in cameras_by_id.items():
                    frame = camera.get_latest_frame()
                    if frame is not None:
                        frame_queues_by_camera[camera_id].put(frame)



        except Exception as e:
            logger.error(f"Camera IDs {camera_ids} Internal Capture Process Failed")
            traceback.print_exc()
            raise e
        finally:
            # close cameras on exit
            for camera_id, camera in cameras_by_id.items():
                logger.info(f"Closing camera {camera.camera_id}")
                camera.close()

    def _create_cameras(self, camera_ids: List[str]) -> Dict[str, Camera]:
        cameras = {}
        for camera_id in camera_ids:
            cameras[camera_id] = Camera(CameraConfig(camera_id=camera_id))
        return cameras
