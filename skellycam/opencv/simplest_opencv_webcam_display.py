"""
Connect to camera at port '0' and display in a loop - close with ESC

requires `opencv-python` or `opencv-contrib-python`

note - should run in any environment that can run `freemocap` stuff
"""
import time

import cv2
import numpy as np

camera_id = 0
cap = cv2.VideoCapture(camera_id)

should_continue = True

start_time = time.perf_counter()
timestamps = []
while should_continue:

    success, image = cap.read()

    timestamps.append(time.perf_counter() - start_time)
    median_framerate = np.median(np.diff(timestamps)) ** -1

    print(
        f"read image success: {success} , image.shape: {image.shape}, median_framerate: {median_framerate}"
    )
    cv2.imshow(f"Camera {camera_id} - Press ESC to exit", image)

    if cv2.waitKey(1) == 27:
        print(f"ESC key pressed - shutting down")
        cv2.destroyAllWindows()

        should_continue = False
