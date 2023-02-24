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
    def timestamps(self) -> List[Union[int, float]]:
        return self._gather_timestamps(self._frame_list)

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
            self._frames_per_second = np.nanmedian((np.diff(np.asarray(self._timestamps, 'float')) ** -1)) * 1e9

            self._cv2_video_writer = self._initialize_video_writer(
                image_height=frame_chunk[0].image.shape[0],
                image_width=frame_chunk[0].image.shape[1],
                frames_per_second=self._frames_per_second,
                path_to_save_video_file=self._video_file_save_path
            )

        # save this chunk to the file
        self._write_frame_list_to_video_file(frame_payload_list=frame_chunk, release_writer=False)

        if final_chunk:
            logger.info("This is the final chunk of frames we're going to get -  saving timestamps and releasing video writer")
            self._save_timestamps(timestamps_npy=self._timestamps,
                                  video_file_save_path=self._video_file_save_path)
            self._cv2_video_writer.release()

    def save_frame_list_to_video_file(
            self,
            video_file_save_path: Union[str, Path],
            frame_payload_list: List[FramePayload],
            frames_per_second: float = None,
    ):

        if frames_per_second is None:
            self._timestamps = self._gather_timestamps(frame_payload_list)
            try:
                frames_per_second = (
                        np.nanmedian((np.diff(np.asarray(self._timestamps,'float')) ** -1)) * 1e9
                )
            except Exception as e:
                logger.debug("Error calculating frames per second")
                traceback.print_exc()
                raise e

        self._cv2_video_writer = self._initialize_video_writer(
            image_height=frame_payload_list[0].image.shape[0],
            image_width=frame_payload_list[0].image.shape[1],
            frames_per_second=frames_per_second,
            path_to_save_video_file=video_file_save_path,
        )
        self._write_frame_list_to_video_file(frame_payload_list=frame_payload_list)
        self._save_timestamps(timestamps_npy=self._timestamps, video_file_save_path=video_file_save_path)
        self._cv2_video_writer.release()

    def save_image_list_to_disk(
            self,
            image_list: List[np.ndarray],
            path_to_save_video_file: Union[str, Path],
            frames_per_second: float,
    ):

        if len(image_list) == 0:
            logging.error(f"No frames to save for : {path_to_save_video_file}")
            return

        self._cv2_video_writer = self._initialize_video_writer(
            image_height=image_list[0].shape[0],
            image_width=image_list[0].shape[1],
            frames_per_second=frames_per_second,
            path_to_save_video_file=path_to_save_video_file,
        )
        self._write_image_list_to_video_file(image_list)

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

        return timestamps

    def _save_timestamps(self,
                         timestamps_npy: List[Union[float, int]],
                         video_file_save_path: Union[str, Path]):

        video_file_save_path = Path(video_file_save_path)
        timestamp_folder_path = Path(video_file_save_path).parent / "timestamps"
        timestamp_folder_path.mkdir(parents=True, exist_ok=True)

        base_timestamp_path_str = str(
            timestamp_folder_path / video_file_save_path.stem
        )

        # save timestamps to npy (binary) file (via numpy.ndarray)
        path_to_save_timestamps_npy = base_timestamp_path_str + "_binary.npy"
        np.save(str(path_to_save_timestamps_npy), np.asarray(timestamps_npy, 'float'))

        logger.info(f"Saved timestamps to path: {str(path_to_save_timestamps_npy)}")

        # save timestamps to human readable (csv/text) file (via pandas.DataFrame)
        path_to_save_timestamps_csv = (
                base_timestamp_path_str + "_timestamps_human_readable.csv"
        )
        timestamp_dataframe = pd.DataFrame(timestamps_npy)
        timestamp_dataframe.to_csv(str(path_to_save_timestamps_csv))
        logger.info(f"Saved timestamps to path: {str(path_to_save_timestamps_csv)}")
