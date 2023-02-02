import logging
import time

import cv2
import numpy as np

from skellycam.detection.private.found_camera_cache import FoundCameraCache
from skellycam.opencv.config.determine_backend import determine_backend

CAM_CHECK_NUM = 20  # please give me a reason to increase this number ;D

logger = logging.getLogger(__name__)

MIN_RESOLUTION_CHECK = 0   # the lowest width value that will be used to determine the minimum resolution of the camera
MAX_RESOLUTION_CHECK = 10000   # the highest width value that will be used to determine the maximum resolution of the camera
RESOLUTION_CHECK_STEPS = 10 # the number of 'slices" between the minimum and maximum resolutions that will be checked to determine the possible resolutions

class DetectPossibleCameras:
    def find_available_cameras(self) -> FoundCameraCache:
        cv2_backend = determine_backend()

        cams_to_use_list = []
        caps_list = []
        for cam_id in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(cam_id, cv2_backend)
            success, image1 = cap.read()
            time0 = time.perf_counter()

            if not success:
                continue

            if image1 is None:
                continue

            try:
                success, image2 = cap.read()
                time1 = time.perf_counter()

                # TODO: This cant work. Needs a new solution
                if time1 - time0 > 0.5:
                    logger.debug(
                        f"Camera {cam_id} took {time1 - time0} seconds to produce a 2nd "
                        f"frame. It might be a virtual camera Skipping it."
                    )
                    continue  # skip to next port number

                if np.mean(image2) > 10 and np.sum((image1-image2).ravel()) == 0:
                    logger.debug(
                        f"Camera {cam_id} appears to be return identical non-black frames -its  probably a virtual camera, skipping"
                    )
                    continue  # skip to next port number

                logger.debug(
                    f"Camera found at port number {cam_id}: success={success}, "
                    f"image.shape={image1.shape},  cap={cap}"
                )
                cams_to_use_list.append(str(cam_id))
                caps_list.append(cap)
            except Exception as e:
                logger.error(
                    f"Exception raised when looking for a camera at port{cam_id}: {e}"
                )

        for cap in caps_list:
            logger.debug(f"Releasing cap {cap}")
            cap.release()
            logger.debug(f"Deleting cap {cap}")
            del cap

        logger.debug(f"Deleting caps_list {caps_list}")
        del caps_list

        logger.info(f"Found cameras: {cams_to_use_list}")
        return FoundCameraCache(
            number_of_cameras_found=len(cams_to_use_list),
            cameras_found_list=cams_to_use_list,
        )

    def get_nearest_resolution(self, video_capture, target_width):
        """
        returns the resolution nearest the target width for a given cv2.VideoCapture object
        """
        
        # 1. store the current resolution of the VideoCapture object
        current_width = video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        current_height = video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        # 2. attempt to set its width to the provided width argument
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
        
        # 3. determine which resolution the VideoCapture object goes to
        nearest_width = video_capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        nearest_height = video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        # 4. reset the VideoCapture object to the original resolution
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, current_width)
        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, current_height)

        # 5. return the resolution as a tuple of (width, height)
        return (nearest_width, nearest_height) 

    def get_possible_resolutions(self, video_capture):
        pass
        

if __name__ == "__main__":
    detector = DetectPossibleCameras()
    camera_cache = detector.find_available_cameras()
    print("hello world")
    