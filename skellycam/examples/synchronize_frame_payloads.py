import asyncio
import logging
import time
import multiprocessing
import pandas as pd
from queue import Queue
from pathlib import Path
import cv2

from skellycam.detection.detect_cameras import detect_cameras
from skellycam.opencv.group.camera_group import CameraGroup
from skellycam.system.environment.default_paths import default_session_folder_path
from skellycam.opencv.group.synchronizer import Synchronizer

logger = logging.getLogger(__name__)


def show_synched_frames(camera_ids_list: list = None):

    if camera_ids_list is None:
        camera_ids_list = [0]

    camera_group = CameraGroup(camera_ids_list)
    camera_group.start()
    should_continue = True

    # will be receiving a bundle of synched frames via queue
    syncr = Synchronizer(camera_ids_list)
    bundle_q = Queue()
    syncr.subscribe_to_bundle(bundle_q)

    # bundle data and frame times are just for summary reporting...saved to csv in default session folder path
    bundle_index = 0
    bundle_data = {"Bundle": []}

    for port in camera_ids_list:
        bundle_data[f"Port_{port}_Time"] = []

    frame_times = {"port": [], "frame_index": [], "frame_time": []}

    for p in multiprocessing.active_children():
        print(f"before big frame loop - found child process: {p}")

    while should_continue:
        latest_frame_payloads = camera_group.latest_frames()

        for cam_id, frame_payload in latest_frame_payloads.items():
            if frame_payload is not None:
                syncr.add_frame_payload(
                    frame_payload
                )  # the line that does something; give synchronizer a payload

                # dictionary below is just to create summary output
                frame_times["port"].append(frame_payload.camera_id)
                frame_times["frame_index"].append(frame_payload.frame_number)
                frame_times["frame_time"].append(frame_payload.timestamp_ns)

        if not bundle_q.empty():

            # when a synched bundle is available, the synchronizer pushes it out to subscribed queues
            # if there is something on the queue, grab it...
            new_bundle = bundle_q.get()

            # the section below is just for display and summary output
            bundle_data["Bundle"].append(bundle_index)
            bundle_index += 1
            for port, frame_data in new_bundle.items():
                if frame_data:
                    cv2.imshow(f"Port {port}", frame_data["frame"]) #display frames just to make sure it's working
                    bundle_data[f"Port_{port}_Time"].append(frame_data["frame_time"])
                else:
                    bundle_data[f"Port_{port}_Time"].append("dropped")

        if cv2.waitKey(1) == 27:
            logger.info(f"ESC key pressed - shutting down")
            cv2.destroyAllWindows()
            should_continue = False

    camera_group.close()

    # export summary output
    frame_times = pd.DataFrame(frame_times)
    frame_times.to_csv(
        Path(default_session_folder_path(create_folder=True), "frame_times.csv")
    )

    bundle_data = pd.DataFrame(bundle_data)
    bundle_data.to_csv(
        Path(default_session_folder_path(create_folder=True), "bundle_data.csv")
    )


if __name__ == "__main__":
    found_camera_response = detect_cameras()
    camera_ids_list_in = found_camera_response.cameras_found_list

    # asyncio.run(show_synched_frames(camera_ids_list_in))
    show_synched_frames(camera_ids_list_in)

    print("done!")
