import time

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("qt5agg")

from fast_camera_capture.opencv.group.camera_group import CameraGroup


if __name__ == "__main__":
    cam_ids = ["0", "1","2", "3", "4", "5", "6"]
    g = CameraGroup(cam_ids)
    g.start()

    timestamps_dictionary = {}
    frame_payload_dictionary = {}

    loop_time = time.perf_counter_ns()

    break_after_n_frames = 100

    while True:
        prev_loop_time = loop_time
        loop_time = time.perf_counter_ns()
        loop_duration = (loop_time - prev_loop_time) / 1e6

        for cam_id in cam_ids:
            if cam_id not in timestamps_dictionary:
                timestamps_dictionary[cam_id] = []
            if cam_id not in frame_payload_dictionary:
                frame_payload_dictionary[cam_id] = []

            frame_payload = g.get_by_cam_id(cam_id)

            if frame_payload is not None:
                if len(timestamps_dictionary[cam_id]) > 0:
                    is_this_a_new_frame = timestamps_dictionary[cam_id][-1] != frame_payload.timestamp_ns
                else:
                    is_this_a_new_frame = False
                    frame_payload_dictionary[cam_id] = frame_payload
                    timestamps_dictionary[cam_id].append(frame_payload.timestamp_ns)

                if is_this_a_new_frame:
                    frame_payload_dictionary[cam_id] = frame_payload
                    timestamps_dictionary[cam_id].append(frame_payload.timestamp_ns)
                    is_this_a_new_frame = False

        print(f"Loop duration: {loop_duration:.3} ms: Timestamps: {[len(val) for val in timestamps_dictionary.values()]}")

        if len(timestamps_dictionary[cam_id]) > break_after_n_frames:
            break

    # plot timestamps
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10, 10))
    max_frame_duration = 0.1
    for cam_id, timestamps in timestamps_dictionary.items():
        timestamps_formatted = np.asarray(timestamps) - timestamps[0]
        timestamps_formatted = timestamps_formatted / 1e9

        ax1.plot(timestamps_formatted, label=cam_id)
        ax1.set_xlabel("Frame number")
        ax1.set_ylabel("Time from zero (sec)")
        ax1.legend()

        ax2.plot(np.diff(timestamps_formatted),'.', label=cam_id)
        ax2.set_xlabel("Frame number")
        ax2.set_ylabel("Frame duration (sec)")
        ax2.legend()


        ax3.hist(np.diff(timestamps_formatted), bins=np.arange(0, max_frame_duration, 0.0025),label=cam_id)
        ax3.set_xlabel("Frame duration (ms)")
        ax3.set_ylabel("count")
        ax3.legend()

    plt.show()


