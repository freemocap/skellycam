import json
import logging
import time
from pathlib import Path
from typing import Dict, Union

import cv2

from skellycam import CameraConfig
from skellycam.detection.detect_cameras import detect_cameras
from skellycam.detection.models.frame_payload import FramePayload
from skellycam.diagnostics.framerate_diagnostics import (
    calculate_camera_diagnostic_results,
    create_timestamp_diagnostic_plots,
)
from skellycam.diagnostics.plot_first_and_last_frames import plot_first_and_last_frames
from skellycam.opencv.group.camera_group import CameraGroup
from skellycam.opencv.video_recorder.save_synchronized_videos import (
    save_synchronized_videos,
)
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.system.environment.default_paths import (
    default_base_folder,
    default_session_name,
    get_iso6201_time_string,
)

logger = logging.getLogger(__name__)


class MultiCameraVideoRecorder:
    def __init__(
        self,
        video_save_folder_path: Union[str, Path] = None,
        camera_config_dict: Dict[str, CameraConfig] = None,
        string_tag: str = None,
    ):
        self._session_start_time_iso8601 = get_iso6201_time_string()
        self._session_start_time_unix_seconds = time.time()
        self._session_name = default_session_name(string_tag=string_tag)

        if video_save_folder_path is None:
            self._video_save_folder_path = default_base_folder() / self._session_name
        else:
            self._video_save_folder_path = Path(video_save_folder_path)
        self._video_save_folder_path.mkdir(parents=True, exist_ok=True)

        self._camera_ids_list = detect_cameras().cameras_found_list
        time.sleep(0.1)

        self._shared_zero_time = time.perf_counter_ns()

        if camera_config_dict is None:
            self._camera_config_dict = {
                cam_id: CameraConfig(camera_id=cam_id)
                for cam_id in self._camera_ids_list
            }
        else:
            self._camera_config_dict = camera_config_dict

        self._camera_group = CameraGroup(
            camera_ids_list=self._camera_ids_list,
            camera_config_dictionary=self._camera_config_dict,
        )

        self._video_recorder_dictionary = {}
        self._qt_multi_camera_viewer_thread = None

    def run(self):

        self._camera_group.start()

        for camera_id in self._camera_ids_list:
            self._video_recorder_dictionary[camera_id] = VideoRecorder()

        self._run_frame_loop()

        # save videos
        self._synchronized_frame_list_dictionary = save_synchronized_videos(
            dictionary_of_video_recorders=self._video_recorder_dictionary,
            folder_to_save_videos=self._video_save_folder_path,
        )

        self._create_diagnostic_plots()
        self._save_session_information()

    def _create_diagnostic_plots(self):
        # get timestamp diagnostics
        timestamps_dictionary = {}
        for cam_id, video_recorder in self._video_recorder_dictionary.items():
            timestamps_dictionary[cam_id] = (
                video_recorder.timestamps - self._shared_zero_time
            )

        self._timestamp_diagnostics = calculate_camera_diagnostic_results(
            timestamps_dictionary
        )

        print(self._timestamp_diagnostics.dict())

        diagnostic_plot_file_path = (
            Path(self._video_save_folder_path) / "timestamp_diagnostic_plots.png"
        )
        create_timestamp_diagnostic_plots(
            raw_frame_list_dictionary=self._copy_frame_payload_lists(),
            synchronized_frame_list_dictionary=self._synchronized_frame_list_dictionary,
            path_to_save_plots_png=diagnostic_plot_file_path,
            open_image_after_saving=True,
        )

        plot_first_and_last_frames(
            synchronized_frame_list_dictionary=self._synchronized_frame_list_dictionary,
            path_to_save_plots_png=Path(self._video_save_folder_path)
            / "first_and_last_frames.png",
            open_image_after_saving=True,
        )

    def _run_frame_loop(self):
        logger.info(f"Starting frame loop")
        should_continue = True
        while should_continue:
            latest_frame_payloads = self._camera_group.latest_frames()

            for cam_id, frame_payload in latest_frame_payloads.items():
                if frame_payload is not None:
                    self._video_recorder_dictionary[
                        cam_id
                    ].append_frame_payload_to_list(frame_payload)

                    self._show_image(frame_payload)

            frame_count_dictionary = {}

            for cam_id, video_recorder in self._video_recorder_dictionary.items():
                frame_count_dictionary[cam_id] = video_recorder.number_of_frames
            print(f"{frame_count_dictionary}")

            if cv2.waitKey(1) == 27:
                logger.info(f"ESC key pressed - shutting down")
                cv2.destroyAllWindows()

                should_continue = False
        self._camera_group.close()

    def _copy_frame_payload_lists(self) -> Dict[str, list]:
        raw_frame_list_dictionary = {}
        for camera_id, video_recorder in self._video_recorder_dictionary.items():
            raw_frame_list_dictionary[
                camera_id
            ] = video_recorder._frame_payload_list.copy()
        return raw_frame_list_dictionary

    def _create_session_information_dict(self):
        session_information_dictionary = {
            "read_me": f"This file contains the information relevant to session: {self._session_name}",
            "session_details": self._get_session_details_dict(),
            "camera_configurations": {},
            "timestamp_diagnostic_results": self._timestamp_diagnostics.dict(),
        }

        for camera_id, camera_config in self._camera_config_dict.items():
            session_information_dictionary["camera_configurations"][
                camera_id
            ] = camera_config.dict()

        return session_information_dictionary

    def _get_session_details_dict(self):
        return {
            "session_name": self._session_name,
            "session_start_time_iso8601": self._session_start_time_iso8601,
            "session_start_time_unix_seconds": self._session_start_time_unix_seconds,
            "video_save_folder_path": str(self._video_save_folder_path),
        }

    def _save_session_information(self):
        session_information_dictionary = self._create_session_information_dict()
        json_path = self._video_save_folder_path / "session_information.json"
        with open(json_path, "w") as file:
            json_string = json.dumps(session_information_dictionary, indent=4)
            logger.info(f"Saving session information to {json_path}")
            file.write(json_string)

    def _show_image(self, frame_payload: FramePayload):
        cv2.imshow(
            f"Camera {frame_payload.camera_id} - Press ESC to quit", frame_payload.image
        )


if __name__ == "__main__":
    synchronized_video_recorder = MultiCameraVideoRecorder()
    synchronized_video_recorder.run()
