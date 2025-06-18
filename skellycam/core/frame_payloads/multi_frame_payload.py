import numpy as np
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.frame_payload import FramePayload, initialize_frame_rec_array
from skellycam.core.frame_payloads.multi_frame_metadata import MultiFrameMetadata
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import create_multiframe_dtype
from skellycam.core.types.type_overloads import CameraIdString


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
    dummy_timebase_mapping = TimebaseMapping()  # NOTE - dummy value - used for shape, size, dtype etc
    for camera_id, config in camera_configs.items():
        # Store the image and metadata for this camera
        data[camera_id] = initialize_frame_rec_array(camera_config=config,
                                                     timebase_mapping=dummy_timebase_mapping,
                                                     frame_number=frame_number)

    # Create the record array with the multiframe dtype
    return np.rec.array(
        tuple(data.values()),
        dtype=create_multiframe_dtype(camera_configs)
    )


class MultiFramePayload(BaseModel):
    frames: dict[CameraIdString, FramePayload | None]

    @classmethod
    def create_empty(cls, camera_configs: CameraConfigs) -> "MultiFramePayload":
        return cls(frames={camera_id: None for camera_id in camera_configs.keys()})

    def to_metadata(self) -> "MultiFrameMetadata":
        """
        Convert the MultiFramePayload to a MultiFrameMetadata object.
        """
        return MultiFrameMetadata.from_multi_frame_payload(self)

    @property
    def timebase_mapping(self) -> TimebaseMapping:
        self._validate_multi_frame()  # This ensures the payload is full

        # Get frames that are not None
        valid_frames = [frame for frame in self.frames.values() if frame is not None]

        if not valid_frames:
            raise ValueError("MultiFramePayload has no valid frames")

        # Get the first timebase mapping as reference
        reference_mapping = valid_frames[0].frame_metadata.timestamps.timebase_mapping

        # Check if all other mappings are equal to the reference
        for frame in valid_frames[1:]:
            current_mapping = frame.frame_metadata.timestamps.timebase_mapping
            if current_mapping != reference_mapping:
                raise ValueError(f"MultiFramePayload has multiple timebase mappings")

        return reference_mapping

    @property
    def camera_configs(self) -> CameraConfigs:
        return {camera_id: frame.frame_metadata.camera_config for camera_id, frame in self.frames.items() if
                frame is not None}

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
        return self._validate_multi_frame()

    def _validate_multi_frame(self) -> int:
        if not self.full:
            raise ValueError("MultiFramePayload is not full, cannot get multi_frame_number")
        frame_numbers = [frame.frame_metadata.frame_number for frame in self.frames.values()]
        mf_number = set(frame_numbers)
        if len(mf_number) > 1:
            raise ValueError(f"MultiFramePayload has multiple frame numbers {mf_number}")
        return mf_number.pop()

    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the MultiFramePayload to a numpy record array.
        """
        self._validate_multi_frame()
        # Create a record array with the correct shape (1,)
        dtype = create_multiframe_dtype(self.camera_configs)
        result = np.recarray(1, dtype=dtype)

        # Assign each camera's data to the corresponding field
        for camera_id, frame in self.frames.items():
            result[camera_id][0] = frame.to_numpy_record_array()[0]

        return result

    @classmethod
    def from_numpy_record_array(cls, mf_rec_array: np.recarray) -> "MultiFramePayload":
        frames = {}
        for camera_id in mf_rec_array.dtype.names:
            frames[camera_id] = FramePayload.from_numpy_record_array(mf_rec_array[camera_id])

        instance = cls(frames=frames)
        instance._validate_multi_frame()
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
                raise ValueError(
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
        self._validate_multi_frame()
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
