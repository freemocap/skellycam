import logging
import multiprocessing
import time
from pathlib import Path
from typing import Dict, Optional

import cv2
from skellytracker.utilities.get_video_paths import get_video_paths

from skellycam.core.camera_group.camera.config.image_resolution import ImageResolution
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.playback.video_config import VideoConfig, VideoConfigs

logger = logging.getLogger(__name__)

# TODO: make pydantic model/dataclass
class VideoPlayback:
    """
    Reads video from file into MultiFramePayloads

    Use with a context manager, like:
    with VideoReader() as video_reader:
        while video_reader.current_payload is not None:
            queue.put(video_reader.current_payload)
            time.sleep(self.frame_duration)
            video_reader.next_frame_payload()
    """

    def __init__(self, synchronized_video_folder_path: str | Path):
        self.synchronized_video_folder_path = Path(synchronized_video_folder_path)
        self.index_to_path_map = self.create_index_to_path_map()
        self.video_captures = self.load_video_captures()
        self.video_configs = self.create_video_configs()

        self.current_payload = self.create_initial_payload()

    def create_index_to_path_map(self):  # I didn't make this a property in case user edits folder while running
        return {index: path for index, path in
                enumerate(get_video_paths(path_to_video_folder=self.synchronized_video_folder_path))}

    def load_video_captures(self) -> Dict[int, cv2.VideoCapture]:
        return {
            index: cv2.VideoCapture(str(video_path)) for index, video_path in self.index_to_path_map.items()
        }

    def create_video_configs(self) -> VideoConfigs:
        video_configs = {}
        for camera_id, capture in self.video_captures.items():
            color_channels = 1 if capture.get(cv2.CAP_PROP_MONOCHROME) else 3
            video_configs[camera_id] = VideoConfig(
                camera_id=camera_id,
                camera_name=self.index_to_path_map[camera_id].stem,
                resolution=ImageResolution(height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                                           width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
                color_channels=color_channels,
                framerate=capture.get(cv2.CAP_PROP_FPS),
                capture_fourcc=capture.get(cv2.CAP_PROP_FOURCC)
            )
        return video_configs

    @property
    def fps(self) -> float:
        fps = {cap.get(cv2.CAP_PROP_FPS) for cap in self.video_captures.values()}

        if len(fps) != 1:
            # TODO: is this worth validating? or if frames counts match we don't care
            raise RuntimeError(f"All fps values do not match: {fps}")

        return fps.pop()

    @property
    def frame_duration(self) -> float:
        return 1 / self.fps

    def close_video_captures(self):
        for video_capture in self.video_captures.values():
            video_capture.release()

    def create_initial_payload(self):
        initial_payload = MultiFramePayload.create_initial(camera_configs=self.video_configs)
        for camera_id, video_capture in self.video_captures.items():
            ret, frame = video_capture.read()
            if not ret:
                logger.error(f"Failed to read frame {self.current_payload.multi_frame_number} for camera {camera_id}")
                self.close_video_captures()
                raise RuntimeError(f"Unable to load first frame from ")
            metadata = create_empty_frame_metadata(camera_id=camera_id, frame_number=0,
                                                   config=self.video_configs[camera_id])
            frame = FramePayload.create(image=frame, metadata=metadata)

            initial_payload.add_frame(frame)
        return initial_payload

    def next_frame_payload(self) -> Optional[MultiFramePayload]:
        payload = MultiFramePayload.from_previous(camera_configs=self.video_configs)

        for camera_id, video_capture in self.video_captures.items():
            ret, frame = video_capture.read()
            if not ret:  # temporary limit for testing
                print(f"Failed to read frame {self.current_payload.multi_frame_number} for camera {camera_id}")
                print("Closing video captures")
                self.close_video_captures()
                self.current_payload = None  # this ensures None is stuffed into Queue to signal processing is done, could be a better way to do this
                return None  # TODO: call an end_video function, based off how skellycam normally ends things
            metadata = create_empty_frame_metadata(camera_id=camera_id, frame_number=payload.multi_frame_number,
                                                   config=self.camera_configs[camera_id])
            frame = FramePayload.create(image=frame, metadata=metadata)

            payload.add_frame(frame)

        self.current_payload = payload
        return payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_video_captures()


def read_video_into_queue(synchronized_video_path: Path, camera_payload_queue: multiprocessing.Queue) -> None:
    with VideoPlayback(synchronized_video_folder_path=synchronized_video_path) as video_reader:
        while video_reader.current_payload is not None:
            camera_payload_queue.put(video_reader.current_payload)
            time.sleep(1 / video_reader.frame_duration)
            video_reader.next_frame_payload()

    camera_payload_queue.put(None)

    print("processed entire recording!")
