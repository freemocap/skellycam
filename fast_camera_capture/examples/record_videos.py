import asyncio
import logging
from pathlib import Path

import cv2

from fast_camera_capture.detection.detect_cameras import detect_cameras
from fast_camera_capture.examples.framerate_diagnostics import calculate_camera_diagnostic_results, \
    show_timestamp_diagnostic_plots
from fast_camera_capture.opencv.group.camera_group import CameraGroup
from fast_camera_capture.opencv.video_recorder.video_recorder import VideoRecorder

logger = logging.getLogger(__name__)


async def record_synchronized_videos(camera_ids_list: list, save_path: str | Path):
    camera_group = CameraGroup(camera_ids_list)
    shared_zero_time = time.perf_counter_ns()
    camera_group.start()
    should_continue = True

    video_recorder_dictionary = {}
    for camera_id in camera_ids_list:
        video_recorder_dictionary[camera_id] = VideoRecorder()

    while should_continue:
        latest_frame_payloads = camera_group.latest_frames()
        for cam_id, frame_payload in latest_frame_payloads.items():
            if frame_payload is not None:
                video_recorder_dictionary[cam_id].append_frame_payload_to_list(frame_payload)
                cv2.imshow(f"Camera {cam_id} - Press ESC to quit", frame_payload.image)

        frame_count_dictionary = {}
        for cam_id, video_recorder in video_recorder_dictionary.items():
            frame_count_dictionary[cam_id] = video_recorder.number_of_frames
        print(f"{frame_count_dictionary}")

        if cv2.waitKey(1) == 27:
            logger.info(f"ESC key pressed - shutting down")
            cv2.destroyAllWindows()
            should_continue = False

    camera_group.close()

    # get timestamp diagnostics
    timestamps_dictionary = {}
    for cam_id, video_recorder in video_recorder_dictionary.items():
        timestamps_dictionary[cam_id] = video_recorder.timestamps
    timestamp_diagnostic_data_class = calculate_camera_diagnostic_results(timestamps_dictionary)
    print(timestamp_diagnostic_data_class.__dict__)
    show_timestamp_diagnostic_plots(timestamps_dictionary, shared_zero_time, save_path, show_plot=False)

    # save videos
    for cam_id, video_recorder in video_recorder_dictionary.items():
        logger.info(f"Saving video for camera {cam_id}")
        video_file_name = Path(save_path) / f"camera_{cam_id}_unsynchronized.mp4"
        video_recorder.save_video_to_file(video_file_name)


if __name__ == "__main__":
    import time

    found_camera_response = detect_cameras()
    camera_ids_list_in = found_camera_response.cameras_found_list

    save_path_in = Path.home() / 'fast-camera-capture-recordings' / time.strftime("%m-%d-%Y_%H_%M_%S")
    save_path_in.mkdir(parents=True, exist_ok=True)
    asyncio.run(record_synchronized_videos(camera_ids_list=camera_ids_list_in, save_path=save_path_in))

    print('done!')
