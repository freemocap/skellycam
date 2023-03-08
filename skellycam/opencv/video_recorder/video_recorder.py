import logging
import traceback
from pathlib import Path
from typing import List, Union

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class VideoRecorder:

    def __init__(self, video_file_save_path: Union[str, Path] = None):

        self._cv2_video_writer = None
        self._video_file_save_path = video_file_save_path
        self._frame_list: List[FramePayload] = []
        self._timestamps = []
        self._frames_per_second = None

    @property
    def timestamps(self) -> np.ndarray:
        assert len(self._frame_list) > 0, "There are no frames in the frame list"
        return np.asarray(self._gather_timestamps(self._frame_list), 'float')

    @property
    def frames_per_second(self) -> float:

        fps = 1 / (self.median_frame_duration_ns / 1e9)

        if np.isinf(fps):
            raise Exception("frames_per_second is inf...")

        return fps

    @property
    def median_frame_duration_ns(self) -> np.ndarray:
        return np.nanmedian(np.diff(self.timestamps))

    @property
    def number_of_frames(self) -> int:
        return len(self._frame_list)

    @property
    def frame_list(self) -> List[FramePayload]:
        return self._frame_list

    @frame_list.setter
    def frame_list(self, frame_list: List[FramePayload]):
        self._frame_list = frame_list

    def close(self):
        self._cv2_video_writer.release()

    def append_frame_payload_to_list(self, frame_payload: FramePayload):
        self._frame_list.append(frame_payload)

    def save_frame_chunk_to_video_file(self, frame_chunk: List[FramePayload], final_chunk: bool = False):

        self._timestamps.extend(self._gather_timestamps(frame_chunk))

        if self._cv2_video_writer is None:
            self._cv2_video_writer = self._initialize_video_writer(
                image_height=frame_chunk[0].image.shape[0],
                image_width=frame_chunk[0].image.shape[1],
                frames_per_second=self.frames_per_second,
                path_to_save_video_file=self._video_file_save_path
            )

        # save this chunk to the file
        self._write_frame_list_to_video_file(frame_payload_list=frame_chunk, release_writer=False)

        if final_chunk:
            logger.info(
                "This is the final chunk of frames we're going to get -  saving timestamps and releasing video writer")
            self._save_timestamps(timestamps_npy=self.timestamps,
                                  video_file_save_path=self._video_file_save_path)
            self._cv2_video_writer.release()

    def save_frame_list_to_video_file(
            self,
            video_file_save_path: Union[str, Path] = None,
            frame_payload_list: List[FramePayload] = None,
    ):

        if video_file_save_path is None:
            video_file_save_path = self._video_file_save_path

        if frame_payload_list is None:
            frame_payload_list = self._frame_list

        if video_file_save_path is None or frame_payload_list is None:
            raise ValueError("`video_file_save_path` and `frame_payload_list` are both `None`.")

        height = frame_payload_list[0].image.shape[0]
        width = frame_payload_list[0].image.shape[1]
        frames_per_second = self.frames_per_second

        logging.info(f"Saving {len(frame_payload_list)} frames to {video_file_save_path}, "
                     f"video height : {height}, "
                     f"video width : {width}, "
                     f"frames per second : {frames_per_second}")

        try:
            assert not np.isnan(height) and not np.isinf(height), f"Height is: { height }"
            assert not np.isnan(width) and not np.isinf(width), f"Width is: { width }"
            assert not np.isnan(frames_per_second) and not np.isinf(frames_per_second), f"Frames per second is: { frames_per_second }"
        except AssertionError as e:
            logger.error(f"Assertion error: {e}")
            logger.error(traceback.format_exc())
            raise e



        self._cv2_video_writer = self._initialize_video_writer(
            image_height=height,
            image_width=width,
            frames_per_second=frames_per_second,
            path_to_save_video_file=video_file_save_path,
        )
        self._write_frame_list_to_video_file(frame_payload_list=frame_payload_list)
        self._save_timestamps(timestamps_npy=self.timestamps, video_file_save_path=video_file_save_path)
        self._cv2_video_writer.release()

    def _initialize_video_writer(
            self,
            image_height: Union[int, float],
            image_width: Union[int, float],
            path_to_save_video_file: Union[str, Path],
            frames_per_second: Union[int, float] = None,
            fourcc: str = "mp4v",
            # calibration_videos: bool = False,
    ) -> cv2.VideoWriter:

        video_writer_object = cv2.VideoWriter(
            str(path_to_save_video_file),
            cv2.VideoWriter_fourcc(*fourcc),
            frames_per_second,
            (int(image_width), int(image_height)),
        )

        if not video_writer_object.isOpened():
            logger.error(
                f"cv2.VideoWriter failed to initialize for: {str(path_to_save_video_file)}"
            )
            raise Exception("cv2.VideoWriter is not open")

        return video_writer_object

    def _write_frame_list_to_video_file(self, frame_payload_list: List[FramePayload], release_writer: bool = True):

        try:
            for frame in tqdm(
                    frame_payload_list,
                    desc=f"Saving video: {self._video_file_save_path}",
                    total=len(frame_payload_list),
                    colour="cyan",
                    unit="frames",
                    dynamic_ncols=True,
                    leave=False,
            ):
                self._cv2_video_writer.write(frame.image)

        except Exception as e:
            logger.error(
                f"Failed during save in video writer for video {str(self._video_file_save_path)}"
            )
            traceback.print_exc()
            raise e

        if release_writer:
            logger.debug(f"Releasing video writer for {self._video_file_save_path}")
            self._cv2_video_writer.release()

    def _write_image_list_to_video_file(self, image_list: List[np.ndarray]):
        try:
            for image in image_list:
                self._cv2_video_writer.write(image)
        except Exception as e:
            logger.error(
                f"Failed during save in video writer for video {str(self._video_file_save_path)}"
            )
            traceback.print_exc()
            raise e
        finally:
            self._cv2_video_writer.release()

    def _gather_timestamps(self, frame_payload_list: List[FramePayload]) -> List[Union[int, float]]:
        timestamps = []

        for frame_payload in frame_payload_list:
            timestamps.append(frame_payload.timestamp_ns)

        if len(timestamps) == 0:
            raise Exception("No timestamps found in frame payload list.")

        return timestamps

    def _save_timestamps(self,
                         timestamps_npy: np.ndarray,
                         video_file_save_path: Union[str, Path]):

        video_file_save_path = Path(video_file_save_path)
        timestamp_folder_path = Path(video_file_save_path).parent / "timestamps"
        timestamp_folder_path.mkdir(parents=True, exist_ok=True)

        base_timestamp_path_str = str(
            timestamp_folder_path / video_file_save_path.stem
        )

        # save timestamps to npy (binary) file (via numpy.ndarray)
        path_to_save_timestamps_npy = base_timestamp_path_str + "_binary.npy"
        np.save(str(path_to_save_timestamps_npy), timestamps_npy)

        logger.info(f"Saved timestamps to path: {str(path_to_save_timestamps_npy)}")

        # save timestamps to human readable (csv/text) file (via pandas.DataFrame)
        path_to_save_timestamps_csv = (
                base_timestamp_path_str + "_timestamps_human_readable.csv"
        )
        timestamp_dataframe = pd.DataFrame(timestamps_npy)
        timestamp_dataframe.to_csv(str(path_to_save_timestamps_csv))
        logger.info(f"Saved timestamps to path: {str(path_to_save_timestamps_csv)}")
