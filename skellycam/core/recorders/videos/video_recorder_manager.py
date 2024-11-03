import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Any

from pydantic import BaseModel, ValidationError, Field

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp
from skellycam.core.recorders.timestamps.multiframe_timestamp_logger import MultiframeTimestampLogger
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.video_recorder import VideoRecorder

# TODO - Create a 'recording folder schema' of some kind specifying the structure of the recording folder
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
TIMESTAMPS_FOLDER_NAME = "synchronized_videos"

SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME = f"{SYNCHRONIZED_VIDEOS_FOLDER_NAME}_README.md"

# TODO - Flesh out the README content
SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT = f"""# Synchronized Videos Folder
This folder contains the synchronized videos and timestamps for a recording session.

Each video in this folder should have precisely the same number of frames, each of which corresponds to the same time period across all cameras (i.e. 'frame 12 in camera 1' should represent an image of the same moment in time as 'frame 12 in camera 2' etc.) 
"""

logger = logging.getLogger(__name__)


class VideoRecorderManager(BaseModel):
    recording_uuid: str = str(uuid.uuid4())
    recording_folder: str
    recording_name: str
    camera_configs: CameraConfigs
    fresh: bool = True

    video_recorders: Dict[CameraId, VideoRecorder]
    multi_frame_timestamp_logger: MultiframeTimestampLogger

    class Config:
        arbitrary_types_allowed = True

    @property
    def recording_info(self) -> "RecordingInfo":
        return RecordingInfo.from_video_recorder_manager(self)

    @property
    def number_of_frames_to_save(self) -> int:
        return sum([video_recorder.number_of_frames_to_write for video_recorder in self.video_recorders.values()])

    @property
    def frames_to_save(self) -> bool:
        return self.number_of_frames_to_save > 0

    @classmethod
    def create(cls,
               multi_frame_payload: MultiFramePayload,
               camera_configs: CameraConfigs,
               recording_folder: str):

        logger.debug(f"Creating FrameSaver for recording folder {recording_folder}")

        recording_name = Path(recording_folder).name
        videos_folder = str(Path(recording_folder) / SYNCHRONIZED_VIDEOS_FOLDER_NAME)
        video_recorders = {}
        for camera_id, config in camera_configs.items():
            video_recorders[camera_id] = VideoRecorder.create(frame=multi_frame_payload.get_frame(camera_id),
                                                              recording_name=recording_name,
                                                              videos_folder=videos_folder,
                                                              config=camera_configs[camera_id],
                                                              )

        return cls(recording_folder=recording_folder,
                   recording_name=recording_name,
                   camera_configs=camera_configs,
                   video_recorders=video_recorders,
                   multi_frame_timestamp_logger=MultiframeTimestampLogger.create(video_save_directory=videos_folder,
                                                                                 recording_name=recording_name)
                   )

    def add_multi_frame(self, mf_payload: MultiFramePayload):
        logger.loop(f"Adding multi-frame {mf_payload.multi_frame_number} to video recorder for:  {self.recording_name}")
        self._validate_multi_frame(mf_payload=mf_payload)
        for camera_id in mf_payload.camera_ids:
            frame = mf_payload.get_frame(camera_id)
            self.video_recorders[camera_id].add_frame(frame=frame)
        self.multi_frame_timestamp_logger.log_multiframe(multi_frame_payload=mf_payload)

    def save_one_frame(self) -> Optional[bool]:
        """
        saves one frame from one video recorder
        """
        if not self.frames_to_save:
            return
        if not Path(self.recording_folder).exists():
            self._create_video_recording_folder()

        frame_counts = {camera_id: video_recorder.number_of_frames_to_write for camera_id, video_recorder in self.video_recorders.items()}
        camera_id_to_save = max(frame_counts, key=frame_counts.get)
        tik = time.perf_counter_ns()
        frame_number = self.video_recorders[camera_id_to_save].write_one_frame()
        tok = time.perf_counter_ns()
        if frame_number is None:
            raise RuntimeError(f"Frame number is None after writing frame to video recorder for camera {camera_id_to_save}")
        if camera_id_to_save == 0:
            print("\n------------------------------------")
        print(f"Camera {camera_id_to_save} wrote frame {frame_number} to file (write took: {(tok - tik)/1e6:.3f}ms)")
        return True


    def _save_folder_readme(self):
        with open(str(Path(self.recording_folder) / SYNCHRONIZED_VIDEOS_FOLDER_README_FILENAME), "w") as f:
            f.write(SYNCHRONIZED_VIDEOS_FOLDER_README_CONTENT)

    def _validate_multi_frame(self, mf_payload: MultiFramePayload):
        # Note - individual VideoRecorders will validate the frames' resolutions and whatnot
        if not self.camera_configs.keys() == mf_payload.frames.keys():
            raise ValidationError(f"CameraConfigs and MultiFramePayload frames do not match")

    def _create_video_recording_folder(self):
        Path(self.videos_folder).mkdir(parents=True, exist_ok=True)

    def finish_and_close(self):
        logger.debug(f"Finishing up...")
        finish_threads = []
        for recorder in self.video_recorders.values():
            finish_threads.append(threading.Thread(target=recorder.finish_and_close))
        for thread in finish_threads:
            thread.start()
        for thread in finish_threads:
            thread.join()
        self.close()

    def close(self):
        logger.debug(f"Closing {self.__class__.__name__} for recording: `{self.recording_name}`")
        for video_saver in self.video_recorders.values():
            video_saver.close()
        self.multi_frame_timestamp_logger.close()
        self.finalize_recording()

    def finalize_recording(self):
        logger.debug(f"Finalizing recording: `{self.recording_name}`...")
        self.finalize_timestamps()
        self.save_recording_summary()
        self.validate_recording()
        # self._save_folder_readme() # TODO - uncomment this when ready, only save if recording is successful
        logger.success(f"Recording `{self.recording_name} Successfully recorded to: {self.recording_folder}")

    def finalize_timestamps(self):
        # TODO - add clean up and optional tasks... calc stats, save to individual cam timestamp files, etc
        pass

    def save_recording_summary(self):
        # TODO - Update the `recording_info` with the final recording info? Or maybe a separeate `RecordingStats` save?
        # Save the recording info to a `[recording_name]_info.json` in the recording folder
        self.recording_info.save_to_file()

    def validate_recording(self):
        # TODO - validate the recording, like check that there are the right numbers of videos and timestamps and whatnot
        pass


