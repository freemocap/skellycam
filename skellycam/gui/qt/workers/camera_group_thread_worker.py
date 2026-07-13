import logging
import time
from pathlib import Path
from typing import List, Union

import cv2
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QImage
from skellycam.detection.charuco.charuco_definition import CHARUCO_BOARDS, charuco_7x5
from skellycam.detection.charuco.charuco_detection import draw_charuco_on_image

from skellycam.detection.models.frame_payload import FramePayload
from skellycam.gui.qt.workers.video_save_thread_worker import VideoSaveThreadWorker
from skellycam.opencv.camera.types.camera_id import CameraId
from skellycam.opencv.group.camera_group import CameraGroup
from skellycam.opencv.video_recorder.video_recorder import VideoRecorder
from skellycam.opencv.video_recorder.streaming_video_writer import WriterFailedError, WriterSaturatedError

logger = logging.getLogger(__name__)


class CamGroupThreadWorker(QThread):
    new_image_signal = Signal(CameraId, QImage, dict)
    cameras_connected_signal = Signal()
    cameras_closed_signal = Signal()
    camera_group_created_signal = Signal(dict)
    videos_saved_to_this_folder_signal = Signal(str)

    def __init__(
            self,
            camera_ids: Union[List[str], None],
            get_new_synchronized_videos_folder_callable: callable,
            annotate_images: bool = False,
            parent=None,
    ):

        self._synchronized_video_folder_path = None
        logger.info(
            f"Initializing camera group frame worker with camera ids: {camera_ids}"
        )
        super().__init__(parent=parent)
        self._camera_ids = camera_ids
        self._get_new_synchronized_videos_folder_callable = get_new_synchronized_videos_folder_callable
        self.annotate_images = annotate_images

        self._should_pause_bool = False
        self._should_record_frames_bool = False

        self._updating_camera_settings_bool = False
        self._current_recording_name = None
        self._video_save_process = None

        # Global synchronized frame index. Assigned once per committed
        # multi-camera frame bundle (see run()), not per camera -- this is
        # what lets every camera's writer agree on the same frame identity
        # without needing every frame resident in RAM for post-hoc matching.
        self._next_frame_index = 0

        # Real-time approximation of the old post-hoc nearest-timestamp
        # match, applied per-bundle instead of across a full in-RAM buffer.
        # Deliberately NOT proven equivalent for multi-camera use -- see
        # _try_record_synchronized_frame_bundle()'s docstring. 50ms is a
        # provisional default (roughly 1.5 frame periods at 30fps); tune
        # after real multi-camera jitter is measured.
        self._max_frame_bundle_timestamp_delta_ns = 50_000_000

        self._charuco_board = charuco_7x5()

        if self._camera_ids is not None:
            self._camera_group = self._create_camera_group(self._camera_ids)
            self._video_recorder_dictionary = (
                self._initialize_video_recorder_dictionary()
            )
        else:
            self._camera_group = None
            self._video_recorder_dictionary = None

    @property
    def camera_ids(self):
        return self._camera_ids

    @camera_ids.setter
    def camera_ids(self, camera_ids: List[str]):
        self._camera_ids = camera_ids

        if self._camera_ids is not None:
            if self._camera_group is not None:
                while self._camera_group.is_capturing:
                    self._camera_group.close()
                    time.sleep(0.1)

        self._camera_group = self._create_camera_group(self._camera_ids)
        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()

    @property
    def slot_dictionary(self):
        """
        dictionary of slots to attach to signals in QtMultiCameraControllerWidget
        NOTE - `keys` must match those in QtMultiCameraControllerWidget.button_dictionary
        """
        return {
            "play": self.play,
            "pause": self.pause,
            "start_recording": self.start_recording,
            "stop_recording": self.stop_recording,
        }

    @property
    def camera_config_dictionary(self):
        return self._camera_group.camera_config_dictionary

    @property
    def cameras_connected(self):
        return self._camera_group.is_capturing

    @property
    def is_recording(self):
        return self._should_record_frames_bool

    @property
    def charuco_board(self):
        return self._charuco_board
    
    @charuco_board.setter
    def charuco_board(self, charuco_name: str):
        if charuco_name in CHARUCO_BOARDS:
            self._charuco_board = CHARUCO_BOARDS[charuco_name]()
            logger.info(f"Set charuco board to {charuco_name}")
        else:
            logger.error(f"Charuco board {charuco_name} not found in CHARUCO_BOARDS.")

    def run(self):
        logger.info("Starting camera group thread worker")
        self._camera_group.start()
        should_continue = True

        logger.info("Emitting `cameras_connected_signal`")
        self.cameras_connected_signal.emit()

        while self._camera_group.is_capturing and should_continue:
            if self._updating_camera_settings_bool:
                continue

            frame_payload_dictionary = self._camera_group.latest_frames()

            if self._should_record_frames_bool and not self._should_pause_bool:
                self._try_record_synchronized_frame_bundle(frame_payload_dictionary)

            for camera_id, frame_payload in frame_payload_dictionary.items():
                if frame_payload:
                    if not self._should_pause_bool:
                        if self.annotate_images:
                            draw_charuco_on_image(image=frame_payload.image, charuco_board=self.charuco_board)

                        q_image = self._convert_frame(frame_payload)

                        frame_diagnostic_dictionary = {}
                        frame_diagnostic_dictionary["mean_frames_per_second"] = frame_payload.mean_frames_per_second,
                        frame_diagnostic_dictionary["frames_received"] = frame_payload.number_of_frames_received,
                        frame_diagnostic_dictionary["queue_size"] = self._camera_group.queue_size[camera_id]

                        try:
                            frame_diagnostic_dictionary["frames_recorded"] = self._video_recorder_dictionary[
                                camera_id].number_of_frames
                        except KeyError:
                            frame_diagnostic_dictionary["frames_recorded"] = 0
                        except Exception as e:
                            logger.error(f"Error getting frame count for camera {camera_id}: {e}")

                        self.new_image_signal.emit(camera_id, q_image, frame_diagnostic_dictionary)

    def _try_record_synchronized_frame_bundle(self, frame_payload_dictionary: dict) -> None:
        """Commit one synchronized frame bundle per poll iteration: either
        every enabled camera's writer receives this iteration's frame under
        the same global frame_index, or none of them do.

        IMPORTANT (see ARCHITECTURE_REPORT.md / STREAMING_RECORDING_ARCHITECTURE.md
        for the full analysis): CameraGroup.latest_frames() is a per-camera
        independent queue pop with NO cross-camera timestamp comparison --
        the capture-loop poll was never a synchronization boundary in the
        original design. The original algorithm synchronized post-hoc, at
        save time, via nearest-timestamp matching across each camera's full
        in-RAM buffer -- which this rewrite deliberately removes (that's the
        memory bug). "Same poll iteration" alone is therefore NOT equivalent
        to that original guarantee: a backlogged frame from a slow camera
        could otherwise be paired with a fresh frame from a fast one under
        the same frame_index. The max-timestamp-delta check below is a
        real-time approximation of the same intent, not a proven-equivalent
        replacement -- multi-camera correctness under this design is
        deliberately treated as IMPROVED BUT UNVALIDATED, not proven, and a
        dedicated multi-camera synchronization test is required before this
        is trusted for real multi-camera recordings. This incident and this
        sprint's live testing are single-camera only, where this distinction
        does not apply (there is nothing to pair against).
        """
        # Stable order owned by the worker (dict insertion order, set once by
        # _initialize_video_recorder_dictionary) -- iterating a set directly
        # gives non-deterministic order, which makes failure-ordering
        # unreproducible for no benefit.
        camera_ids_in_order = list(self._video_recorder_dictionary.keys())
        expected_camera_ids = set(camera_ids_in_order)
        available_camera_ids = {
            camera_id for camera_id, payload in frame_payload_dictionary.items() if payload
        }
        if not expected_camera_ids.issubset(available_camera_ids):
            return  # partial bundle this iteration -- wait for the next one, never commit it

        if len(camera_ids_in_order) > 1:
            timestamps_ns = [
                frame_payload_dictionary[camera_id].timestamp_ns for camera_id in camera_ids_in_order
            ]
            max_delta_ns = max(timestamps_ns) - min(timestamps_ns)
            if max_delta_ns > self._max_frame_bundle_timestamp_delta_ns:
                logger.debug(
                    "Skipping frame bundle -- cameras not sufficiently synchronized this "
                    f"iteration (max_delta_ns={max_delta_ns} > "
                    f"threshold={self._max_frame_bundle_timestamp_delta_ns}). This is an "
                    "expected, non-fatal skip under multi-camera jitter, not a failure."
                )
                return  # not a synchronized instant -- skip, never commit it under a shared index

        frame_index = self._next_frame_index
        self._next_frame_index += 1

        submitted_camera_ids = []
        try:
            for camera_id in camera_ids_in_order:
                self._video_recorder_dictionary[camera_id].append_frame_payload_to_list(
                    frame_payload_dictionary[camera_id], frame_index=frame_index,
                )
                submitted_camera_ids.append(camera_id)
        except (WriterSaturatedError, WriterFailedError) as exc:
            logger.error(
                f"Recording writer failure at frame_index={frame_index} "
                f"({len(submitted_camera_ids)}/{len(camera_ids_in_order)} cameras already "
                f"committed this frame before the failure): {exc}"
            )
            self._abort_recording(reason=str(exc))

    def _abort_recording(self, reason: str) -> None:
        """Honest failure path for queue saturation or writer death: every
        camera's writer is aborted together so the recording never claims
        partial success. Partial files are preserved by StreamingVideoWriter;
        this method just makes sure nothing keeps submitting to a doomed
        recording and that a fresh, empty set of recorders is ready for the
        next Start."""
        logger.error(f"Aborting synchronized recording: {reason}")
        self._should_record_frames_bool = False
        for camera_id, video_recorder in self._video_recorder_dictionary.items():
            if video_recorder.is_streaming:
                try:
                    video_recorder.abort_streaming(reason=reason)
                except RuntimeError:
                    pass  # already finished (e.g. this was the camera whose failure triggered the abort)
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Error aborting recorder for camera {camera_id}: {exc}")
        self._synchronized_video_folder_path = None
        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()

    def _convert_frame(self, frame: FramePayload):
        image = frame.image
        # image = cv2.flip(image, 1)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        converted_frame = QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            QImage.Format.Format_RGB888,
        )

        return converted_frame.scaled(int(image.shape[1] / 2), int(image.shape[0] / 2),
                                      Qt.AspectRatioMode.KeepAspectRatio)

    def close(self):
        logger.info("Closing camera group")
        try:
            self._camera_group.close(cameras_closed_signal=self.cameras_closed_signal)
        except AttributeError:
            pass

    def pause(self):
        logger.info("Pausing image display")
        self._should_pause_bool = True

    def play(self):
        logger.info("Resuming image display")
        self._should_pause_bool = False

    def start_recording(self):
        logger.info("Starting recording")
        if self.cameras_connected:
            if self._synchronized_video_folder_path is None:
                self._synchronized_video_folder_path = self._get_new_synchronized_videos_folder_callable()

            # Writer opened here, at Start, not deferred to Stop -- this is
            # what makes recording duration stop determining RAM usage.
            self._next_frame_index = 0
            for camera_id, video_recorder in self._video_recorder_dictionary.items():
                config = self._camera_group.camera_config_dictionary[camera_id]
                output_path = Path(self._synchronized_video_folder_path) / (
                    f"Camera_{str(camera_id).zfill(3)}_synchronized.mp4"
                )
                video_recorder.start_streaming(
                    video_file_save_path=output_path,
                    expected_fps=float(config.framerate),
                )

            self._should_record_frames_bool = True
        else:
            logger.warning("Cannot start recording - cameras not connected")

    def stop_recording(self):
        logger.info("Stopping recording")
        self._should_record_frames_bool = False
        self._launch_save_video_thread_worker()

    def update_camera_group_configs(self, camera_config_dictionary: dict):
        if self._camera_ids is None:
            self._camera_ids = list(camera_config_dictionary.keys())

        if self._camera_group is None:
            self._camera_group = self._create_camera_group(
                camera_ids=self.camera_ids,
                camera_config_dictionary=camera_config_dictionary,
            )
            return

        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()
        self._updating_camera_settings_bool = True
        self._updating_camera_settings_bool = not self._update_camera_settings(
            camera_config_dictionary
        )

    def _launch_save_video_thread_worker(self):
        logger.info("Launching save video thread worker")

        synchronized_videos_folder = self._synchronized_video_folder_path
        self._synchronized_video_folder_path = None

        # Ownership transfer, not deepcopy: hand the already-streaming
        # recorders (writer handles, bounded queues, small metadata -- no
        # frame image data) straight to the background finalize worker, and
        # immediately give the capture path a fresh, empty set of recorders
        # for the next recording. This removes the Stop-time doubling of the
        # frame buffer that was the acute trigger of the original freeze --
        # see ARCHITECTURE_REPORT.md.
        video_recorders_to_save = {
            camera_id: video_recorder
            for camera_id, video_recorder in self._video_recorder_dictionary.items()
            if video_recorder.is_streaming
        }
        self._video_recorder_dictionary = self._initialize_video_recorder_dictionary()

        if not video_recorders_to_save:
            logger.warning("No active recorders to save -- nothing was recorded")
            self.videos_saved_to_this_folder_signal.emit(str(synchronized_videos_folder))
            return

        self._video_save_thread_worker = VideoSaveThreadWorker(
            dictionary_of_video_recorders=video_recorders_to_save,
            folder_to_save_videos=str(synchronized_videos_folder),
            create_diagnostic_plots_bool=True,
        )
        self._video_save_thread_worker.start()
        self._video_save_thread_worker.finished_signal.connect(
            self._handle_videos_save_thread_worker_finished
        )

    def _handle_videos_save_thread_worker_finished(self, folder_path: str):
        logger.debug(f"Emitting `videos_saved_to_this_folder_signal` with string: {folder_path}")
        self.videos_saved_to_this_folder_signal.emit(folder_path)

    def _initialize_video_recorder_dictionary(self):
        video_recorder_dictionary = {}
        for camera_id, config in self._camera_group.camera_config_dictionary.items():
            if config.use_this_camera:
                video_recorder_dictionary[camera_id] = VideoRecorder()
        return video_recorder_dictionary

    def _get_recorder_frame_count_dict(self):
        return {
            camera_id: recorder.number_of_frames
            for camera_id, recorder in self._video_recorder_dictionary.items()
        }

    def _create_camera_group(
            self, camera_ids: List[Union[str, int]], camera_config_dictionary: dict = None
    ):
        logger.info(
            f"Creating `camera_group` for camera_ids: {camera_ids}, camera_config_dictionary: {camera_config_dictionary}"
        )

        camera_group = CameraGroup(
            camera_ids_list=camera_ids,
            camera_config_dictionary=camera_config_dictionary,
        )
        self.camera_group_created_signal.emit(camera_group.camera_config_dictionary)
        return camera_group

    def _update_camera_settings(self, camera_config_dictionary: dict):
        try:
            self._camera_group.update_camera_configs(camera_config_dictionary)

        except Exception as e:
            logger.error(f"Problem updating camera settings: {e}")

        return True
