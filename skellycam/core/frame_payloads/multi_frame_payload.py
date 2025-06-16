import time
from pprint import pprint
from typing import Type

import numpy as np
from pydantic import BaseModel, Field
from pydantic import ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.image_rotation_types import RotationTypes
from skellycam.core.frame_payloads.frame_payload import FramePayload, create_frame_dtype, initialize_frame_rec_array
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
from skellycam.core.recorders.timestamps.timebase_mapping import TimeBaseMapping
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.rotate_image import rotate_image

MULTI_FRAME_DTYPE = np.dtype


def create_multiframe_dtype(camera_configs: dict[str, CameraConfig]) -> MULTI_FRAME_DTYPE:
    """
    Create a numpy dtype for multiple frames based on a dictionary of camera configurations.
    Each camera gets its own field in the dtype.

    Args:
        camera_configs: Dictionary mapping camera IDs to their configurations

    Returns:
        A numpy dtype that can store frames from multiple cameras
    """
    fields = []
    for camera_id, config in camera_configs.items():
        # Create a field for each camera using its ID as the field name
        # Each field contains a frame with the camera-specific dtype
        fields.append((camera_id, create_frame_dtype(config)))
    return np.dtype(fields, align=True)


def initialize_multi_frame_rec_array(camera_configs: dict[str, CameraConfig], frame_number: int) -> np.recarray:
    """
    Initialize a record array for multiple frames based on camera configurations.

    Args:
        camera_configs: Dictionary mapping camera IDs to their configurations
        frame_number: The frame number to initialize the metadata with

    Returns:
        A numpy record array that can store frames from multiple cameras
    """
    # Create a dictionary to hold the data for each camera
    data = {}

    for camera_id, config in camera_configs.items():
        # Store the image and metadata for this camera
        data[camera_id] = initialize_frame_rec_array(camera_config=config,
                                                     frame_number=frame_number)

    # Create the record array with the multiframe dtype
    return np.rec.array(
        tuple(data.values()),
        dtype=create_multiframe_dtype(camera_configs)
    )

class MultiFramePayload(BaseModel):
    frames: dict[CameraIdString, FramePayload | None]
    timebase_mapping: TimeBaseMapping = Field(default_factory=TimeBaseMapping, description=TimeBaseMapping.__doc__)

    @property
    def camera_configs(self) -> CameraConfigs:
        return {camera_id: frame.camera_config for camera_id, frame in self.frames.items() if frame is not None}

    @classmethod
    def create_empty(cls, camera_configs: CameraConfigs):
        return cls(frames={camera_id: None for camera_id in camera_configs.keys()})

    @property
    def full(self) -> bool:
        return all([frame is not None for frame in self.frames.values()])

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.frames.keys())

    @property
    def timestamp_ns(self) -> int:
        """
        Returns the mean timestamp of all frames in the multi-frame payload.
        timebase is time.perf_counter_ns(), use TimeBaseMapping to convert to unix time.
        """
        if not self.full:
            raise ValueError("MultiFramePayload is not full, cannot get timestamp")
        return int(np.mean([frame.timestamp_ns for frame in self.frames.values() if frame is not None]))

    @property
    def multi_frame_number(self) -> int:
        frame_numbers = [frame.metadata.frame_number for frame in self.frames.values()]
        mf_number = set(frame_numbers)
        if len(mf_number) > 1:
            raise ValueError(f"MultiFramePayload has multiple frame numbers {mf_number}")
        return mf_number.pop()

    def to_numpy_record_array(self) -> np.recarray:
        if not self.full:
            raise ValueError("MultiFramePayload is not full, cannot convert to numpy structured array")
        return np.rec.array(
            tuple(frame.to_numpy_record_array() for frame in self.frames.values()),
            dtype=create_multiframe_dtype(self.camera_configs)
        )

    @classmethod
    def from_numpy_record_array(cls, rec_array: np.recarray):
        return cls(
            frames={camera_id: FramePayload.from_numpy_record_array(rec_array[camera_id])
                    for camera_id in rec_array.dtype.names},
        )

    def add_frame(self, new_frame: FramePayload) -> None:

        for frame in self.frames.values():
            if frame:
                if frame.camera_id == new_frame.camera_id:
                    raise ValueError(
                        f"Cannot add frame for camera_id {new_frame.camera_id} to MultiFramePayloadDTO, frame already exists!")
                if not frame.frame_number == new_frame.frame_number:
                    raise ValueError(
                        f"Cannot add frame for camera_id {new_frame.frame_number} to MultiFramePayloadDTO, frame number mismatch!")
                if not frame.frame_metadata.timebase_mapping != new_frame.frame_metadata.timebase_mapping:
                    raise ValueError(
                        f"Cannot add frame for camera_id {new_frame.camera_id} to MultiFramePayloadDTO, timebase mapping mismatch!")
        new_frame.frame_metadata.timestamps.put_into_multi_frame_payload = time.perf_counter_ns()
        self.frames[new_frame.camera_id] = new_frame

    def get_frame(self, camera_id: CameraIdString,return_copy: bool = True) -> FramePayload | None:

        if return_copy:
            frame = self.frames[camera_id].model_copy()
        else:
            frame = self.frames[camera_id]

        if frame is None:
            raise ValueError(f"Cannot get frame for camera_id {camera_id} from MultiFramePayloadDTO, frame is None")

        return frame


    def __str__(self) -> str:
        print_str = f"[multi_frame_number: {self.multi_frame_number}"

        for camera_id, frame in self.frames.items():
            print_str += str(frame)
        print_str += "]"
        return print_str

