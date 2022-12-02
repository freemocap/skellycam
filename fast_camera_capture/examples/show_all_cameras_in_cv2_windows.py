import asyncio
import logging
import multiprocessing

import cv2

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)


async def show_all_cameras_in_cv2_windows():
    found_camera_response = detect_cameras()
    camera_ids_list = found_camera_response.cameras_found_list
    camera_group = CameraGroup(camera_ids_list)
    camera_group.start()
    should_continue = True
    loop = 0

    for p in multiprocessing.active_children():
        print(f"before big frame loop - found child process: {p}")

    while should_continue:
        latest_frame_payloads = camera_group.latest_frames()
        for cam_id, frame_payload in latest_frame_payloads.items():
            if frame_payload is not None:
                cv2.imshow(f"Camera {cam_id} - Press ESC to quit", frame_payload.image)
        if cv2.waitKey(1) == 27:
            for p in multiprocessing.active_children():
                print(f"ESC key pressed - found child process: {p}")

            cv2.destroyAllWindows()
            print('setting exit event')

            should_continue = False

    camera_group.close()




if __name__ == "__main__":
    asyncio.run(show_all_cameras_in_cv2_windows())

    while len(multiprocessing.active_children()) > 0:
        for p in multiprocessing.active_children():
            print(f"at the end - found child process: {p}")

    print('done!')
