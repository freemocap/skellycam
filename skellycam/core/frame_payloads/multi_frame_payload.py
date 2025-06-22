import logging

import numpy as np
from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfigs, validate_camera_configs
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.frame_payloads.multi_frame_metadata import MultiFrameMetadata
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import create_multiframe_dtype
from skellycam.core.types.type_overloads import CameraIdString

logger = logging.getLogger(__name__)


class MultiFramePayload(BaseModel):
    frames: dict[CameraIdString, FramePayload | None]

    @classmethod
    def create_dummy(cls,
                     timebase_mapping: TimebaseMapping,
                     camera_configs: CameraConfigs) -> "MultiFramePayload":
        """
        Create a MultiFramePayload with dummy data for each camera.
        """
        frames = {camera_id: FramePayload.create_initial(camera_config=config,
                                                         timebase_mapping=timebase_mapping)
                  for camera_id, config in camera_configs.items()}
        return cls(frames=frames)

    @classmethod
    def create_empty(cls, camera_configs: CameraConfigs) -> "MultiFramePayload":
        return cls(frames={camera_id: None for camera_id in camera_configs.keys()})

    def to_metadata(self) -> "MultiFrameMetadata":
        """
        Convert the MultiFramePayload to a MultiFrameMetadata object.
        """
        return MultiFrameMetadata.from_multi_frame_payload(self)

    @property
    def camera_configs(self) -> CameraConfigs:
        configs = {camera_id: frame.frame_metadata.camera_config for camera_id, frame in self.frames.items()}
        validate_camera_configs(configs)
        return configs

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
    def earliest_timestamp_ns(self) -> int:
        """
        Return the earliest pre_grab timestamp of all frames in the multi-frame payload.
        """
        if not self.full:
            raise ValueError("MultiFramePayload is not full, cannot get timestamp")
        return int(np.min([frame.frame_metadata.timestamps.pre_frame_grab_ns for frame in self.frames.values() if frame is not None]))
    @property
    def multi_frame_number(self) -> int:
        frame_numbers = [frame.frame_metadata.frame_number for frame in self.frames.values()]
        mf_number = set(frame_numbers)
        if len(mf_number) > 1:
            # raise ValueError(f"MultiFramePayload has multiple frame numbers {mf_number}")
            logger.warning(f"MultiFramePayload has multiple frame numbers {mf_number}")
        return mf_number.pop()

    @property
    def timebase_mapping(self) -> TimebaseMapping:
        mappings = [frame.frame_metadata.timestamps.timebase_mapping for frame in self.frames.values()]
        mapping = set(mappings)
        if len(mapping) > 1:
            raise ValueError(f"MultiFramePayload has multiple frame numbers {mapping}")
        return mapping.pop()

    def validate_multi_frame(self):
        if not self.full:
            raise ValueError("MultiFramePayload is not full, cannot get multi_frame_number")
        _ = self.multi_frame_number
        _ = self.timebase_mapping
        _ = self.camera_configs

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the MultiFramePayload to a numpy record array.
        """
        self.validate_multi_frame()
        # Create a record array with the correct shape (1,)
        dtype = create_multiframe_dtype(self.camera_configs)
        result = np.recarray(1, dtype=dtype)

        # Assign each camera's data to the corresponding field
        for camera_id, frame in self.frames.items():
            result[camera_id][0] = frame.to_numpy_record_array()[0]

        return result

    @classmethod
    def from_numpy_record_array(cls,
                                mf_rec_array: np.recarray,
                                apply_config_rotation:bool=False) -> "MultiFramePayload":
        frames = {}
        for camera_id in mf_rec_array.dtype.names:
            frames[camera_id] = FramePayload.create_from_numpy_record_array(mf_rec_array[camera_id],
                                                                            apply_config_rotation=apply_config_rotation)

        instance = cls(frames=frames)
        instance.validate_multi_frame()
        return instance


    def add_frame(self, new_frame: FramePayload) -> None:
        # Check if this camera_id already exists in the frames
        if new_frame.camera_id in self.frames and self.frames[new_frame.camera_id] is not None:
            raise ValueError(
                f"Cannot add frame for camera_id {new_frame.camera_id} to MultiFramePayload, frame already exists!")

        # Check for frame number consistency with existing frames
        existing_frames = [frame for frame in self.frames.values() if frame is not None]
        if existing_frames:
            # Check frame number consistency
            if any(frame.frame_number != new_frame.frame_number for frame in existing_frames):
                logger.warning(
                    f"Cannot add frame for camera_id {new_frame.camera_id} to MultiFramePayload, frame number mismatch!")

            # Check timebase mapping consistency
            if any(
                    frame.frame_metadata.timestamps.timebase_mapping != new_frame.frame_metadata.timestamps.timebase_mapping
                    for frame in existing_frames):
                raise ValueError(
                    f"Cannot add frame for camera_id {new_frame.camera_id} to MultiFramePayload, timebase mapping mismatch!")

        # Add the frame
        self.frames[new_frame.camera_id] = new_frame

    def get_frame(self, camera_id: CameraIdString, return_copy: bool = True) -> FramePayload:
        self.validate_multi_frame()
        frame = self.frames[camera_id]

        if return_copy:
            return frame.model_copy()
        else:
            return frame

    def __str__(self) -> str:
        if not self.full:
            return f"[multi_frame_number: None, frames: {self.frames}]"

        print_str = f"[multi_frame_number: {self.multi_frame_number}"

        for camera_id, frame in self.frames.items():
            print_str += f", {str(frame)}"
        print_str += "]"
        return print_str
