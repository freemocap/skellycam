import asyncio
import logging
import multiprocessing

import cv2

from skellycam.detection.detect_cameras import detect_cameras
from skellycam.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)


async def show_all_cameras_in_cv2_windows(camera_ids_list: list = None):

    if camera_ids_list is None:
        camera_ids_list = [0]

    camera_group = CameraGroup(camera_ids_list)
    camera_group.start()
    should_continue = True

    for p in multiprocessing.active_children():
        print(f"before big frame loop - found child process: {p}")

    while should_continue:
        latest_frame_payloads = camera_group.latest_frames()
        for cam_id, frame_payload in latest_frame_payloads.items():
            if frame_payload is not None:
                cv2.imshow(f"Camera {cam_id} - Press ESC to quit", frame_payload.image)
        if cv2.waitKey(1) == 27:
            logger.info(f"ESC key pressed - shutting down")
            cv2.destroyAllWindows()
            should_continue = False

    camera_group.close()


if __name__ == "__main__":
    found_camera_response = detect_cameras()
    camera_ids_list_in = found_camera_response.cameras_found_list
    asyncio.run(show_all_cameras_in_cv2_windows(camera_ids_list_in))

    print("done!")
