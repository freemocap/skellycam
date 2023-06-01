import logging
import multiprocessing
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
        should_record_controller:multiprocessing.Value,
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
        frame_counts = {}

        try:
            while True:
                record_frames = should_record_controller.value #only check this once per loop because its shared? Is that right?
                for camera in just_cameras:
                    frame = camera.wait_for_next_frame()
                    if record_frames: #I know this violates the "keep the frame loop as leeeeean as possible" rule, but I think it has to be here to avoid frame accumulation
                        frame_lists_by_camera[camera.camera_id].append(frame)
                    else:
                        frame_lists_by_camera[camera.camera_id][-1] = frame if len(frame_lists_by_camera[camera.camera_id]) > 0 else None
                    frame_counts[camera.camera_id] = len(frame_lists_by_camera[camera.camera_id])#debug, delete when done
                print(f"Frame Counts: {frame_counts}")#debug, delete when done
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
