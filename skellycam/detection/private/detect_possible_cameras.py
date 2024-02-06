import logging
import time

import cv2
import numpy as np

from skellycam.detection.private.found_camera_cache import FoundCameraCache
from skellycam.opencv.config.determine_backend import determine_backend

CAM_CHECK_NUM = 20  # please give me a reason to increase this number ;D
MAX_UNUSED_PORTS = 5

logger = logging.getLogger(__name__)


class DetectPossibleCameras:
    def find_available_cameras(self) -> FoundCameraCache:
        cv2_backend = determine_backend()

        cams_to_use_list = []
        unused_ports = 0
        for cam_id in range(CAM_CHECK_NUM):
            if unused_ports >= MAX_UNUSED_PORTS:
                break
            cap = cv2.VideoCapture(cam_id, cv2_backend)
            if cap is None or not cap.isOpened():
                unused_ports += 1
                continue  # fail fast

            success, image1 = cap.read()
            time0 = time.perf_counter()

            if not success:
                unused_ports += 1
                continue

            if image1 is None:
                unused_ports += 1
                continue

            try:
                success, image2 = cap.read()
                time1 = time.perf_counter()

                # TODO: This cant work. Needs a new solution
                # TODO: Issue with OBS implies we could potentially filter out the NV12 fourcc code for this: https://github.com/obsproject/obs-studio/issues/3635
                # Need to double check that only virtual cameras use NV12 FOURCC
                if time1 - time0 > 0.5:
                    logger.debug(
                        f"Camera {cam_id} took {time1 - time0} seconds to produce a 2nd "
                        f"frame. It might be a virtual camera Skipping it."
                    )
                    unused_ports += 1
                    continue  # skip to next port number

                if np.mean(image2) > 10 and np.sum((image1 - image2).ravel()) == 0:
                    logger.debug(
                        f"Camera {cam_id} appears to be return identical non-black frames -its  probably a virtual camera, skipping"
                    )
                    unused_ports += 1
                    continue  # skip to next port number

                logger.debug(
                    f"Camera found at port number {cam_id}: success={success}, "
                    f"image.shape={image1.shape},  cap={cap}"
                )
                cams_to_use_list.append(str(cam_id))
                cap.release()
                del cap
            except Exception as e:
                logger.error(
                    f"Exception raised when looking for a camera at port{cam_id}: {e}"
                )

        logger.info(f"Found cameras: {cams_to_use_list}")
        return FoundCameraCache(
            number_of_cameras_found=len(cams_to_use_list),
            cameras_found_list=cams_to_use_list,
        )


if __name__ == "__main__":
    DetectPossibleCameras().find_available_cameras()
