import logging
import traceback
from pathlib import Path
from typing import List, Union

import cv2
import numpy as np
import pandas as pd

from skellycam.detection.models.frame_payload import FramePayload

logger = logging.getLogger(__name__)


class VideoRecorder:
    def __init__(self):

        self._cv2_video_writer = None
        self._path_to_save_video_file = None
        self._frame_payload_list: List[FramePayload] = []
        self._timestamps_npy = np.empty(0)

    @property
    def timestamps(self) -> np.ndarray:
        return self._gather_timestamps()

    @property
    def number_of_frames(self) -> int:
        return len(self._frame_payload_list)

    @property
    def frame_payload_list(self) -> List[FramePayload]:
        return self._frame_payload_list

    def close(self):
        self._cv2_video_writer.release()

    def append_frame_payload_to_list(self, frame_payload: FramePayload):
        self._frame_payload_list.append(frame_payload)

    def save_frame_list_to_video_file(
        self,
        path_to_save_video_file: Union[str, Path],
        list_of_frames: List[FramePayload] = None,
        frames_per_second: float = None,
    ):

        if list_of_frames is None:
            list_of_frames = self._frame_payload_list

        if frames_per_second is None:
            self._timestamps_npy = self._gather_timestamps()
            try:
                frames_per_second = (
                    np.nanmedian((np.diff(self._timestamps_npy) ** -1)) * 1e9
                )
            except Exception as e:
                logger.debug("Error calculating frames per second")
                traceback.print_exc()
                raise e

        self._path_to_save_video_file = path_to_save_video_file

        self._cv2_video_writer = self._initialize_video_writer(
            image_height=list_of_frames[0].image.shape[0],
            image_width=list_of_frames[0].image.shape[1],
            frames_per_second=frames_per_second,
        )
        self._write_frame_list_to_video_file()
        self._save_timestamps(timestamps_npy=self._timestamps_npy)
        self._cv2_video_writer.release()

    def _initialize_video_writer(
        self,
        image_height: Union[int, float],
        image_width: Union[int, float],
        frames_per_second: Union[int, float] = None,
        fourcc: str = "mp4v",
        # calibration_videos: bool = False,
    ) -> cv2.VideoWriter:

        video_writer_object = cv2.VideoWriter(
            str(self._path_to_save_video_file),
            cv2.VideoWriter_fourcc(*fourcc),
            frames_per_second,
            (int(image_width), int(image_height)),
        )

        if not video_writer_object.isOpened():
            logger.error(
                f"cv2.VideoWriter failed to initialize for: {str(self._path_to_save_video_file)}"
            )
            raise Exception("cv2.VideoWriter is not open")

        return video_writer_object

    def _write_frame_list_to_video_file(self):
        try:
            for frame in self._frame_payload_list:
                self._cv2_video_writer.write(frame.image)

        except Exception as e:
            logger.error(
                f"Failed during save in video writer for video {str(self._path_to_save_video_file)}"
            )
            traceback.print_exc()
            raise e
        finally:
            logger.info(f"Saved video to path: {self._path_to_save_video_file}")
            self._cv2_video_writer.release()

    def _write_image_list_to_video_file(self, image_list: List[np.ndarray]):
        try:
            for image in image_list:
                self._cv2_video_writer.write(image)
        except Exception as e:
            logger.error(
                f"Failed during save in video writer for video {str(self._path_to_save_video_file)}"
            )
            traceback.print_exc()
            raise e
        finally:
            self._cv2_video_writer.release()

    def _gather_timestamps(self) -> np.ndarray:
        timestamps_npy = np.empty(0)
        try:
            for frame_payload in self._frame_payload_list:
                timestamps_npy = np.append(timestamps_npy, frame_payload.timestamp_ns)
        except Exception as e:
            logger.error("Error gathering timestamps")
            logger.error(e)

        return timestamps_npy

    def _save_timestamps(self, timestamps_npy: np.ndarray):
        timestamp_folder_path = self._path_to_save_video_file.parent / "timestamps"
        timestamp_folder_path.mkdir(parents=True, exist_ok=True)

        base_timestamp_path_str = str(
            timestamp_folder_path / self._path_to_save_video_file.stem
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
