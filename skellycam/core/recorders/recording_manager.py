import logging
import threading
import time
from pathlib import Path

from pydantic import BaseModel, ValidationError

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.timestamps.multiframe_timestamp_logger import MultiframeTimestampLogger
from skellycam.core.recorders.videos.recording_info import RecordingInfo, SYNCHRONIZED_VIDEOS_FOLDER_NAME
from skellycam.core.recorders.videos.video_recorder import VideoRecorder
from skellycam.core.types import CameraIdString

# TODO - Create a 'recording folder schema' of some kind specifying the structure of the recording folder


SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME = f"{SYNCHRONIZED_VIDEOS_FOLDER_NAME}_README.md"

# TODO - Flesh out the README content
SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT = f"""# Synchronized Videos Folder
This folder contains the synchronized videos and timestamps for a recording session.

Each video in this folder should have precisely the same number of frames, each of which corresponds to the same time period across all cameras (i.e. 'frame 12 in camera 1' should represent an image of the same moment in time as 'frame 12 in camera 2' etc.) 
"""

logger = logging.getLogger(__name__)


class RecordingManager(BaseModel):
    recording_info: RecordingInfo
    initial_multi_frame_payload: MultiFramePayload

    video_recorders: dict[CameraIdString, VideoRecorder]
    multi_frame_timestamp_logger: MultiframeTimestampLogger

    class Config:
        arbitrary_types_allowed = True

    @property
    def number_of_frames_to_save(self) -> int:
        return sum([video_recorder.number_of_frames_to_write for video_recorder in self.video_recorders.values()])

    @property
    def frames_to_save(self) -> bool:
        return self.number_of_frames_to_save > 0

    @property
    def camera_configs(self) -> CameraConfigs:
        return self.initial_multi_frame_payload.camera_configs

    @classmethod
    def create(cls,
               recording_info: RecordingInfo,
               initial_multi_frame_payload: MultiFramePayload):

        logger.debug(f"Creating FrameSaver for recording folder {recording_info.recording_name}")

        return cls(recording_info = recording_info,
                   initial_multi_frame_payload=initial_multi_frame_payload,
                   multi_frame_timestamp_logger=MultiframeTimestampLogger(recording_info=recording_info,
                                                                          initial_multi_frame_payload=initial_multi_frame_payload),
                   video_recorders={camera_id: VideoRecorder.create(camera_id=camera_id,
                                                         frame=initial_multi_frame_payload.frames[camera_id],
                                                         recording_info=recording_info,
                                                         config= config,
                                                         ) for camera_id, config in initial_multi_frame_payload.camera_configs.items()}
                   )


    def add_multi_frames(self, multi_frame_payloads: list[MultiFramePayload]):
        """
        Adds multiple multi-frames to the video recorder.
        :param multi_frame_payloads: List of MultiFramePayloads to add.
        """
        for mf_payload in multi_frame_payloads:
            self.add_multi_frame(mf_payload=mf_payload)

    def add_multi_frame(self, mf_payload: MultiFramePayload):
        logger.loop(f"Adding multi-frame {mf_payload.multi_frame_number} to video recorder for:  {self.recording_info.recording_name}")
        self._validate_multi_frame(mf_payload=mf_payload)

        for camera_id in mf_payload.camera_ids:
            frame = mf_payload.get_frame(camera_id)
            self.video_recorders[camera_id].add_frame(frame=frame)
        self.multi_frame_timestamp_logger.log_multiframe(multi_frame_payload=mf_payload)

    def try_save_one_frame(self) -> bool:
        """
        Checks if we are ready to save a frame, and if so, saves one frame.
        """
        if not self.frames_to_save:
            return False

        if not Path(self.recording_info.videos_folder).exists():
            Path(self.recording_info.videos_folder).mkdir(parents=True, exist_ok=True)

        return self.save_one_frame()

    def save_one_frame(self) -> bool:
        """
        saves one frame from one video recorder
        """

        frame_counts = {camera_id: video_recorder.number_of_frames_to_write for camera_id, video_recorder in
                        self.video_recorders.items()}
        camera_id_to_save = max(frame_counts, key=frame_counts.get)
        if not camera_id_to_save in self.video_recorders:
            raise ValueError(f"Camera ID {camera_id_to_save} not found in video recorders")
        tik = time.perf_counter_ns()
        frame_number = self.video_recorders[camera_id_to_save].write_one_frame()
        tok = time.perf_counter_ns()
        if frame_number is None:
            raise RuntimeError(
                f"Frame number is None after writing frame to video recorder for camera {camera_id_to_save}")
        # print(f"Camera {camera_id_to_save} wrote frame {frame_number} to file (write took: {(tok - tik)/1e6:.3f}ms)")
        return True

    def _save_folder_readme(self):
        with open(str(Path(self.recording_info.videos_folder) / SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME), "w") as f:
            f.write(SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT)

    def _validate_multi_frame(self, mf_payload: MultiFramePayload):
        # Note - individual VideoRecorders will validate the frames' resolutions and whatnot
        if not self.camera_configs.keys() == mf_payload.frames.keys():
            raise ValidationError(f"CameraConfigs and MultiFramePayload frames do not match")


    def finish_and_close(self):
        logger.debug(f"Finishing up...")
        finish_threads = []
        while not self.try_save_one_frame():
            time.sleep(0.01)

        for recorder in self.video_recorders.values():
            finish_threads.append(threading.Thread(target=recorder.finish_and_close))
            finish_threads[-1].start()
        for thread in finish_threads:
            thread.join()
        self.close()

    def close(self):
        logger.debug(f"Closing {self.__class__.__name__} for recording: `{self.recording_info.recording_name}`")
        for video_saver in self.video_recorders.values():
            video_saver.close()
        self.finalize_recording()

    def finalize_recording(self):
        logger.debug(f"Finalizing recording: `{self.recording_info.recording_name}`...")
        self.recording_info.save_to_file()
        self.multi_frame_timestamp_logger.close()
        self._save_folder_readme()
        self.validate_recording()
        logger.success(f"Recording `{self.recording_info.recording_name} Successfully recorded to: {self.recording_info.recording_directory}")

    def validate_recording(self):
        logger.warning(
            "Recording validation is not implemented yet. This method should do things like check if all video/timestamp files have the same number of frames, etc.")
        pass
