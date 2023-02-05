import logging
import time
from threading import Thread
from typing import Union

import cv2

from skellycam.detection.private.found_camera_cache import FoundCameraCache

logger = logging.getLogger(__name__)

NUMBER_OF_CAMERAS_TO_CHECK = 20  # please give me a reason to increase this number ;D
MIN_RESOLUTION_CHECK = 0  # the lowest width value that will be used to determine the minimum resolution of the camera
MAX_RESOLUTION_CHECK = 5000  # the highest width value that will be used to determine the maximum resolution of the camera
RESOLUTION_CHECK_STEPS = 10  # the number of 'slices" between the minimum and maximum resolutions that will be checked to determine the possible resolutions


class DetectPossibleCameras:
    def __init__(self):
        self._cameras_to_use_list = []
        self._video_capture_objects_list = []
        self._camera_resolutions_dictionary = {}
        self._assess_camera_threads = {}

    def find_available_cameras(self) -> FoundCameraCache:

        # create a dictionary of threads that will check each port for a real camera
        for camera_id in range(NUMBER_OF_CAMERAS_TO_CHECK):
            self._assess_camera_threads[camera_id] = Thread(target=self._assess_camera, args=[camera_id, ], daemon=True)
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
            possible_resolutions=self._camera_resolutions_dictionary
        )

    def _assess_camera(self, camera_id: Union[str, int]):
        """A worker that can be spun up on it's own thread to sort out whether or not a given port connects to a legitimate camera"""
        video_capture_object = cv2.VideoCapture(camera_id)
        success, image1 = video_capture_object.read()

        if not success:
            return

        if image1 is None:
            return

        possible_resolutions = self._get_possible_resolutions(video_capture_object, camera_id)

        if len(possible_resolutions) == 1:
            logger.debug(
                f"Camera {camera_id} has only one possible resolution...likely virtual"
            )
        else:
            logger.debug(
                f"Camera found at port number {camera_id}: success={success}, "
                f"image.shape={image1.shape},  cap={video_capture_object}"
            )

            self._cameras_to_use_list.append(str(camera_id))
            self._video_capture_objects_list.append(video_capture_object)
            self._camera_resolutions_dictionary[camera_id] = possible_resolutions

    def _get_nearest_resolution(self, video_capture: cv2.VideoCapture, target_width: float):
        """
        returns the resolution nearest the target width for a given cv2.VideoCapture object
        """

        # 1. store the current resolution of the VideoCapture object to reset it later
        current_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        current_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 2. attempt to set its width to the provided target_width
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(target_width))

        # 3. determine which resolution the VideoCapture object is actually able to attain
        nearest_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        nearest_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 4. reset the VideoCapture object to the original resolution
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, current_width)
        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, current_height)

        logger.info(f"Resolution with a width nearest {target_width} is {(nearest_width, nearest_height)}")

        # 5. return the resolution as a tuple of (width, height)
        return (nearest_width, nearest_height)

    def _get_possible_resolutions(self, video_capture: cv2.VideoCapture, cam_id: Union[str, int]):

        minimum_resolution = self._get_nearest_resolution(video_capture, MIN_RESOLUTION_CHECK)
        maximum_resolution = self._get_nearest_resolution(video_capture, MAX_RESOLUTION_CHECK)
        logger.info(f"Minimum resolution of camera at port {cam_id} is {minimum_resolution}")
        logger.info(f"Maximum resolution of camera at port {cam_id} is {maximum_resolution}")

        minimum_width = minimum_resolution[0]
        maximum_width = maximum_resolution[0]

        steps_to_check = 10  # fast to check so cover your bases

        # the size of jump to make before checking on the resolution
        step_size = int((maximum_width - minimum_width) / steps_to_check)

        resolutions = {minimum_resolution, maximum_resolution}

        if maximum_width > minimum_width:  # i.e. only one size avaialable
            for test_width in range(
                    int(minimum_width + step_size), int(maximum_width - step_size), int(step_size)
            ):
                new_res = self._get_nearest_resolution(video_capture, test_width)
                # print(new_res)
                resolutions.add(new_res)
            resolutions = list(resolutions)
            resolutions.sort()
            possible_resolutions = resolutions
        else:
            possible_resolutions = [minimum_resolution]

        logger.info(f"At port {cam_id} the possible resolutions are {possible_resolutions}")

        return possible_resolutions


if __name__ == "__main__":
    detector = DetectPossibleCameras()
    start_time = time.perf_counter()
    camera_cache = detector.find_available_cameras()
    elapsed_time = time.perf_counter() - start_time

    print(f"Elapsed time for camera detection is {round(elapsed_time, 2)} seconds")
