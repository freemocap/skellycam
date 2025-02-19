from dataclasses import dataclass, field
import logging
import multiprocessing
import sys
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

def load_video_configs_from_folder(synchronized_video_folder_path: str | Path) -> VideoConfigs: # this should live elsewhere, and class should just take in VideoConfigs
    video_configs = {}
    for camera_id, path in enumerate(get_video_paths(path_to_video_folder=synchronized_video_folder_path)):
        capture = cv2.VideoCapture(str(path))
        color_channels = 1 if capture.get(cv2.CAP_PROP_MONOCHROME) else 3
        video_configs[camera_id] = VideoConfig(
            camera_id=camera_id,
            camera_name=path.stem,

            resolution=ImageResolution(height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                                        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
            color_channels=color_channels,
            framerate=capture.get(cv2.CAP_PROP_FPS),
            capture_fourcc=int(capture.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, byteorder=sys.byteorder).decode('utf-8'),
            video_path=path
        )
    return video_configs

@dataclass # TODO: switch to pydantic
class VideoPlayback:
    video_configs: VideoConfigs
    current_payload: MultiFramePayload = field(init=False)
    video_captures: Dict[str, cv2.VideoCapture] = field(init=False)
    frame_number: int = field(init=False)
    
    def __post_init__(self):
        self.video_captures = self.load_captures_from_configs()
        self.current_payload = self.create_initial_payload()
    
    def load_captures_from_configs(self) -> Dict[str, cv2.VideoCapture]:
        video_captures = {}
        for video_config in self.video_configs.values():
            video_capture = cv2.VideoCapture(str(video_config.video_path))
            if not video_capture.isOpened():
                raise RuntimeError(f"Failed to open video capture for camera {video_config.camera_id}")
            video_captures[video_config.camera_id] = video_capture

        return video_captures

    @property
    def fps(self) -> float:
        fps = {video.framerate for video in self.video_configs.values()}

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
        self.frame_number = 0
        for camera_id, video_capture in self.video_captures.items():
            ret, frame = video_capture.read()
            if not ret:
                logger.error(f"Failed to read frame 0 for camera {camera_id}")
                self.close_video_captures()
                raise RuntimeError(f"Unable to load first frame from {camera_id}")
            metadata = create_empty_frame_metadata(camera_id=int(camera_id), frame_number=self.frame_number,
                                                   config=self.video_configs[int(camera_id)])
            frame = FramePayload.create(image=frame, metadata=metadata)

            initial_payload.add_frame(frame)
        return initial_payload

    def next_frame_payload(self) -> Optional[MultiFramePayload]:
        if self.current_payload is None:
            raise RuntimeError("Cannot run next_frame_payload when current_payload is None - must be run after create_initial_payload")
        payload = MultiFramePayload.from_previous(camera_configs=self.video_configs, previous=self.current_payload)
        self.frame_number += 1

        for camera_id, video_capture in self.video_captures.items():
            ret, frame = video_capture.read()
            if not ret:
                print(f"Failed to read frame {self.frame_number} for camera {camera_id}")
                # TODO: we might not want to close video captures here
                print("Closing video captures")
                self.close_video_captures()
                self.current_payload = None
                self.frame_number = None
                return None  # TODO: call an end_video function, based off how skellycam normally ends things
            # TODO: need to check if this is incrimenting the multi frame number correctly
            metadata = create_empty_frame_metadata(camera_id=int(camera_id), frame_number=self.frame_number,
                                                   config=self.video_configs[int(camera_id)])
            frame = FramePayload.create(image=frame, metadata=metadata)

            payload.add_frame(frame)

        self.current_payload = payload
        return payload
    
    def go_to_frame(self, frame_number: int):
        # TODO: this can be inaccurate, so maybe make another method of doing this accurately?
        for video_capture in self.video_captures.values():
            video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        self.frame_number = frame_number
        

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_video_captures()


def read_video_into_queue(video_configs: VideoConfigs, camera_payload_queue: multiprocessing.Queue) -> None:
    with VideoPlayback(video_configs=video_configs) as video_playback:
        while video_playback.current_payload is not None:
            camera_payload_queue.put(video_playback.current_payload)
            time.sleep(video_playback.frame_duration)
            video_playback.next_frame_payload()

    print("processed entire recording!")

if __name__ == "__main__":
    video_configs = load_video_configs_from_folder("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/synchronized_videos")
    with VideoPlayback(video_configs=video_configs) as video_playback:
        while video_playback.current_payload is not None:
            print(video_playback.current_payload.multi_frame_number)
            video_playback.next_frame_payload()
