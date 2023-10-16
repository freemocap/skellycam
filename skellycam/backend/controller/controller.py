import traceback
from pathlib import Path
from typing import Dict, Optional

from skellycam import logger
from skellycam.backend.controller.core_functionality.camera_group.camera_group_manager import CameraGroupManager
from skellycam.backend.controller.core_functionality.device_detection.detect_available_cameras import \
    detect_available_cameras
from skellycam.backend.controller.core_functionality.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.data_models.cameras.camera_config import CameraConfig
from skellycam.data_models.cameras.camera_device_info import CameraDeviceInfo
from skellycam.data_models.cameras.camera_id import CameraId
from skellycam.data_models.frame_payload import FramePayload
from skellycam.data_models.request_response_update import Request, Response, CamerasDetected, DetectAvailableCameras, \
    ConnectToCameras

CONTROLLER = None


def get_or_create_controller():
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER


class VideoRecorderManager:
    """
    Creates a dictionary of `video_recorders` and then awaits new_images to be sent to it.
    When it receives a new image, it will stuff it into the appropriate `video_recorder`

    Parameters:
    -----------
    cameras: Dict[str, CameraConfig]
        A dictionary of `CameraConfig` objects, keyed by camera_id
    video_save_directory: str
        The directory to save videos to, videos will be saved to this directory as `[Path(video_save_directory)/Path(video_save_directory).stem]_camera_[camera_id].mp4`

    Methods:
    --------
    handle_new_images(new_images: Dict[str, FramePayload]):
        Takes in a dictionary of `FramePayload` objects, keyed by camera_id
        Stuffs each `FramePayload` into the appropriate `video_recorder` object
    """

    def __init__(self,
                 cameras: Dict[str, CameraConfig],
                 video_save_directory: str = None):
        self._cameras = cameras
        self._video_save_directory = video_save_directory
        self._video_recorders = {camera_id: VideoRecorder(camera_config=camera_config,
                                                          video_save_path=self._make_video_save_path(
                                                              camera_id=camera_id)
                                                          ) for camera_id, camera_config in cameras.items()}

    def handle_new_images(self, new_images: Dict[str, FramePayload]):
        for camera_id, frame_payload in new_images.items():
            self._video_recorders[camera_id].append_frame_payload_to_list(frame_payload=frame_payload)

    def _make_video_save_path(self, camera_id: CameraId):
        """
        So, like,  if self._video_save_directory is "/home/user/videos" and camera_id is "0", then this will return "/home/user/recording_name/recording_name_camera_0.mp4"
        This is a bit redundant, but it will save us from having a thousand `camera0.mp4` videos floating around in our lives
        """
        f = 9
        file_name = f"{Path(self._video_save_directory).stem}_camera_{camera_id}.mp4"
        return str(Path(self._video_save_directory) / file_name)


class Controller:
    camera_group_manager: Optional[CameraGroupManager]
    video_recorder_manager: VideoRecorderManager = None
    available_cameras: Dict[str, CameraDeviceInfo] = None

    def handle_request(self, request: Request) -> Response:
        logger.debug(f"Controller received request:\n {request}")
        response = None
        try:
            match request.__class__:
                case DetectAvailableCameras.__class__:
                    self.available_cameras = detect_available_cameras()
                    logger.debug(f"Detected available self.available_cameras: "
                                 f"{[camera.description for camera in self.available_cameras.values()]}")
                    response = CamerasDetected(success=True,
                                               available_cameras = self.available_cameras)

                case ConnectToCameras.__class__:
                    self.camera_group_manager = CameraGroupManager(camera_configs=request.data["camera_configs"])

                    self.camera_group_manager.start_camera_group()


        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            response = Response(success=False,
                                message_type=MessageTypes.ERROR,
                                data={"error": str(e),
                                      "traceback": traceback.format_exc()})
        finally:
            if response is None:
                response = Response(sucess=False,
                                    data={"message": "No response was generated!"})
            logger.debug(f"Controller generated response: response.success = {response.success}")

        return response
