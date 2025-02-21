from dataclasses import dataclass, field
import logging
import multiprocessing
import time
from typing import Dict, Optional

import cv2

from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import create_empty_frame_metadata
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.playback.video_config import VideoConfigs

logger = logging.getLogger(__name__)

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
        # TODO: if we have timestamps, base off that instead
        fps = {video.framerate for video in self.video_configs.values()}

        if len(fps) != 1:
            # TODO: is this worth validating? or if frames counts match we don't care
            raise RuntimeError(f"All fps values do not match: {fps}")

        return fps.pop()

    @property
    def frame_duration(self) -> float:
        return 1 / self.fps
    
    @property
    def current_frame_number(self) -> int:
        return self.frame_number
    
    @property
    def num_frames(self) -> int:
        num_frames = {video.num_frames for video in self.video_configs.values()}

        if len(num_frames) != 1:
            raise RuntimeError(f"Videos are not synchronized, frame counts do not match: {num_frames}")

        return num_frames.pop()

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
                logger.error(f"Failed to read frame {self.frame_number} for camera {camera_id}")
                # TODO: we might not want to close video captures here
                logger.error("Closing video captures")
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
        if frame_number >= self.num_frames or frame_number < 0:
            raise RuntimeError(f"Frame number {frame_number} is out of bounds for video with {self.num_frames} frames")

        for video_capture in self.video_captures.values():
            video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        self.frame_number = frame_number
        self.next_frame_payload()  # TODO: check if this is needed
        

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_video_captures()
