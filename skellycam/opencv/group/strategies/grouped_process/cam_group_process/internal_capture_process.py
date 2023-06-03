import logging
import multiprocessing
import traceback
from multiprocessing import Process
from typing import Any, Dict, List, Union

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
            frame_databases_per_camera: Dict[str, Dict[Union[str, int], Any]],
            cam_ready_ipc: Dict[str, bool],
            should_record_controller: multiprocessing.Value,
    ):
        logger.info(
            f"Starting frame loop capture in CamGroupProcess for cameras: {camera_ids}"
        )

        setproctitle(self.name)
        cam_by_ids = self._create_cameras(camera_ids)
        just_cameras = cam_by_ids.values()
        self._frame_list_index = 0
        for camera in just_cameras:
            camera.connect()
            cam_ready_ipc[camera.camera_id] = True

        try:
            while True:
                for camera in just_cameras:
                    frame = camera.wait_for_next_frame()
                    frame_database = frame_databases_per_camera[camera.camera_id]
                    self._add_frame_to_database(frame, frame_database)

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

    def _add_frame_to_database(self,
                               frame: FramePayload,
                               frame_database: Dict[str, Union[multiprocessing.Value, List[FramePayload]]],
                               ):
        self._frame_list_index += 1
        if self._frame_list_index >= len(frame_database["frames"]):
            self._frame_list_index = 0

        to_be_overwritten = frame_database["frames"][self._frame_list_index]
        if to_be_overwritten.accessed == True:
            logger.warning("Frame was not accessed before being overwritten!")

        frame_database["frames"][self._frame_list_index] = frame
        frame_database["latest_frame_index"].value = self._frame_list_index
