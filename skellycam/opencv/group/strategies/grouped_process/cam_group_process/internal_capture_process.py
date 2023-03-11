import logging
import traceback
from multiprocessing import Process
from typing import Any, Callable, Dict, Iterable, List, Mapping

from setproctitle import setproctitle

from skellycam import Camera, CameraConfig
from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class InternalCaptureProcess(Process):
    def run(self):
        self._start_capture(*self._args)

    def _start_capture(
        self,
        camera_ids: List[str],
        frame_lists_by_camera: Dict[str, List[FramePayload]],
        cam_ready_ipc: Dict[str, bool],
    ):
        logger.info(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_ids}"
        )

        setproctitle(self.name)
        cam_by_ids = self._create_cameras(camera_ids)
        just_cameras = cam_by_ids.values()
        for camera in just_cameras:
            camera.connect()
            cam_ready_ipc[camera.camera_id] = True

        try:
            while True:
                for camera in just_cameras:
                    frame = camera.wait_for_next_frame()
                    frame_lists_by_camera[camera.camera_id].append(frame)
        except Exception as e:
            logger.error(f"Camera IDs {camera_ids} Internal Capture Process Failed")
            traceback.print_exc()
            raise e
        finally:
            # close cameras on exit
            for camera in just_cameras:
                logger.info(f"Closing camera {camera.camera_id}")
                camera.close()

    def _create_cameras(self, camera_ids: List[str]) -> Dict[str, Camera]:
        cameras = {}
        for camera_id in camera_ids:
            cameras[camera_id] = Camera(CameraConfig(camera_id=camera_id))
        return cameras
