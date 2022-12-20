import logging
import time

import cv2

from skellycam.detection.private.found_camera_cache import FoundCameraCache
from skellycam.opencv.config.determine_backend import determine_backend

CAM_CHECK_NUM = 20  # please give me a reason to increase this number ;D

logger = logging.getLogger(__name__)


class DetectPossibleCameras:
    def find_available_cameras(self) -> FoundCameraCache:
        cv2_backend = determine_backend()

        cams_to_use_list = []
        caps_list = []
        for cam_id in range(CAM_CHECK_NUM):
            cap = cv2.VideoCapture(cam_id, cv2_backend)
            success, image = cap.read()
            time0 = time.perf_counter()

            if not success:
                continue

            if image is None:
                continue

            try:
                success, image = cap.read()
                time1 = time.perf_counter()

                # TODO: This cant work. Needs a new solution
                if time1 - time0 > 0.5:
                    logger.debug(
                        f"Camera {cam_id} took {time1 - time0} seconds to produce a 2nd "
                        f"frame. It might be a virtual camera Skipping it."
                    )
                    continue  # skip to next port number

                logger.debug(
                    f"Camera found at port number {cam_id}: success={success}, "
                    f"image.shape={image.shape},  cap={cap}"
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
