import asyncio
import logging

import cv2

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.opencv.group.camera_group import CameraGroup

logger = logging.getLogger(__name__)

async def show_all_cameras_in_cv2_windows():
    found_camera_response = detect_cameras()
    camera_ids_list = found_camera_response.cameras_found_list
    camera_group = CameraGroup(camera_ids_list)
    camera_group.start()
    print('a')

    print('b')
    while True:
        latest_frame_payloads = camera_group.latest_frames()
        for cam_id, frame_payload in latest_frame_payloads.items():
            if frame_payload is not None:
                cv2.imshow(f"Camera {cam_id} - Press ESC to quit", frame_payload.image)
        if cv2.waitKey(1) == 27:
            cv2.destroyAllWindows()
            print('setting exit event')
            camera_group.exit_event.set()

            break



if __name__ == "__main__":
    asyncio.run(show_all_cameras_in_cv2_windows())
