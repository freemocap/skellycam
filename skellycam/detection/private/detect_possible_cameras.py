import logging
import time
from threading import Thread
from typing import Union

import cv2

from skellycam.detection.private.found_camera_cache import FoundCameraCache
from skellycam.opencv.config.determine_backend import determine_backend

logger = logging.getLogger(__name__)

NUMBER_OF_CAMERAS_TO_CHECK = 20  # please give me a reason to increase this number ;D

class DetectPossibleCameras:
    def __init__(self):
        self._cameras_to_use_list = []
        self._video_capture_objects_list = []
        self._verified_resolutions_dictionary = {}
        self._assess_camera_threads = {}

        self.backend = determine_backend()

    def find_available_cameras(self) -> FoundCameraCache:

        # create a dictionary of threads that will check each port for a real camera
        for camera_id in range(NUMBER_OF_CAMERAS_TO_CHECK):
        # for camera_id in [0]:
            self._assess_camera_threads[camera_id] = Thread(
                target=self._assess_camera,
                args=[
                    camera_id,
                ],
                daemon=True,
            )
            self._assess_camera_threads[camera_id].start()

        # wait for all the threads to finish
        for key, thread in self._assess_camera_threads.items():
            thread.join()

        # due to threads, cam_ids not returned in order, so reorder
        self._cameras_to_use_list.sort(key=int)

        for video_capture_object in self._video_capture_objects_list:
            logger.debug(f"Releasing cap {video_capture_object}")
            video_capture_object.release()
            logger.debug(f"Deleting cap {video_capture_object}")
            del video_capture_object

        logger.debug(f"Deleting caps_list {self._video_capture_objects_list}")
        del self._video_capture_objects_list

        logger.info(f"Found cameras: {self._cameras_to_use_list}")


        return FoundCameraCache(
            number_of_cameras_found=len(self._cameras_to_use_list),
            cameras_found_list=self._cameras_to_use_list,
        )

    def _assess_camera(self, camera_id: Union[str, int]):
        """A worker that can be spun up on it's own thread to sort out whether or not a given port connects to a legitimate camera"""
        video_capture_object = cv2.VideoCapture(camera_id, self.backend)
        # video_capture_object = cv2.VideoCapture(camera_id)
        success, image1 = video_capture_object.read()

        if not success:
            return

        if image1 is None:
            return

        # check a non-viable resolution. If accepted by the video capture object, then likely virtual
        # note that this is the behavior of OpenCV when connecting via CAP_DSHOW on windows
        # but is not the behavior when connecting via CAP_ANY on windows (instead it returns the nearest viable resolution)
        is_virtual, new_resolution = self._check_resolution(
            video_capture_object, camera_id, (599, 599)
        )
        
        if is_virtual:
            logger.info(f"Camera at port {camera_id} is likely virtual")
            return

        self.default_resolution = (image1.shape[1], image1.shape[0])
        # verified_resolutions = self._get_verified_resolutions(
        #     video_capture_object, camera_id
        # )

        logger.debug(
            f"Camera found at port number {camera_id}: success={success}, "
            f"image.shape={image1.shape},  cap={video_capture_object}"
        )

        # reset the VideoCapture object to the original resolution
        video_capture_object.set(cv2.CAP_PROP_FRAME_WIDTH, self.default_resolution[0])
        video_capture_object.set(cv2.CAP_PROP_FRAME_HEIGHT, self.default_resolution[1])

        self._cameras_to_use_list.append(str(camera_id))
        self._video_capture_objects_list.append(video_capture_object)

    def _check_resolution(
        self, video_capture: cv2.VideoCapture, cam_id: int, target_resolution: tuple
    ):
        """
        Determine if a given resolution is viable for a video capture object.
        Returns a tuple:
            - First return: Bool: indicating whether or not the width is viable
            - Second return: if viable, returns (width,height) combo, otherwise second return value is None
        """

        # 2. attempt to set its width to the provided target_width
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(target_resolution[0]))
        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(target_resolution[1]))

        # 3. determine which resolution the VideoCapture object is actually able to attain
        new_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        new_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if (new_width, new_height) == target_resolution:
            logger.info(
                f"At port {cam_id}, camera has a possible resolution of {(new_width, new_height)}"
            )

            return True, (new_width, new_height)
        else:
            logger.info(
                f"At port {cam_id}, the resolution width of {target_resolution} is not supported"
            )
            return False, None


if __name__ == "__main__":
    detector = DetectPossibleCameras()
    start_time = time.perf_counter()
    camera_cache = detector.find_available_cameras()
    elapsed_time = time.perf_counter() - start_time

    print(f"Elapsed time for camera detection is {round(elapsed_time, 2)} seconds")
