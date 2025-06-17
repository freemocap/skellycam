import time

import numpy as np
from pydantic import BaseModel, Field

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.frame_payloads.frame_payload import FramePayload, initialize_frame_rec_array
from skellycam.core.frame_payloads.multi_frame_metadata import MultiFrameMetadata
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import create_multiframe_dtype
from skellycam.core.types.type_overloads import CameraIdString


def initialize_multi_frame_rec_array(camera_configs: dict[str, CameraConfig],frame_number: int) -> np.recarray:
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
    principal_camera_id: CameraIdString = Field(
        description="- The camera ID of the principal camera for this multi-frame payload, used to define timebase within a multiframe."
    )
    frames: dict[CameraIdString, FramePayload | None]

    @classmethod
    def create_empty(cls, camera_configs: CameraConfigs, principal_camera_id: CameraIdString = None) -> "MultiFramePayload":
        if principal_camera_id is None:
            # use lowest camera index as principal camera
            principal_camera_id = sorted(camera_configs.keys(), key=lambda x: camera_configs[x].camera_index)[0]
        return cls(frames={camera_id: None for camera_id in camera_configs.keys()},
                     principal_camera_id=principal_camera_id)

    def to_metadata(self) -> "MultiFrameMetadata":
        """
        Convert the MultiFramePayload to a MultiFrameMetadata object.
        """
        return MultiFrameMetadata.from_multi_frame_payload(self)

    @property
    def timebase_mapping(self) -> TimebaseMapping:
        self._validate_multi_frame()
        timebase_mappings = set([frame.timebase_mapping for frame in self.frames.values()])
        if len(timebase_mappings) != 1:
            raise ValueError(f"MultiFramePayload has multiple timebase mappings: {timebase_mappings}")
        return timebase_mappings.pop()

    @property
    def camera_configs(self) -> CameraConfigs:
        return {camera_id: frame.camera_config for camera_id, frame in self.frames.items() if frame is not None}

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
    def from_numpy_record_array(cls, mf_rec_array: np.recarray):
        frames = {}
        for camera_id in mf_rec_array.dtype.names:
            frames[camera_id] = FramePayload.from_numpy_record_array(mf_rec_array[camera_id])

        instance =  cls(frames=frames)
        instance._validate_multi_frame()
        return instance

    def add_frame(self, new_frame: FramePayload) -> None:

        for frame in self.frames.values():
            if frame:
                if frame.camera_id == new_frame.camera_id:
                    raise ValueError(
                        f"Cannot add frame for camera_id {new_frame.camera_id} to MultiFramePayloadDTO, frame already exists!")
                if not frame.frame_number == new_frame.frame_number and False:
                    raise ValueError(
                        f"Cannot add frame for camera_id {new_frame.frame_number} to MultiFramePayloadDTO, frame number mismatch!")
                if frame.frame_metadata.timebase_mapping != new_frame.frame_metadata.timebase_mapping:
                    raise ValueError(
                        f"Cannot add frame for camera_id {new_frame.camera_id} to MultiFramePayloadDTO, timebase mapping mismatch!")
        new_frame.frame_metadata.timestamps.put_into_multi_frame_payload = time.perf_counter_ns()
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


if __name__ == "__main__":
    import numpy as np
    from skellycam.core.camera.config.camera_config import CameraConfig
    from skellycam.core.camera.config.image_resolution import ImageResolution
    from skellycam.core.frame_payloads.frame_payload import FramePayload
    from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
    from skellycam.core.frame_payloads.frame_timestamps import FrameLifespanTimestamps, MultiframeLifespanTimestamps, \
    MultiframeTimestamps
    from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping

    # Create example camera configurations
    _camera_configs = {
        "cam1": CameraConfig(
            camera_id="cam1",
            camera_index=0,
            camera_name="Camera 1",
            resolution=ImageResolution(width=640, height=480),
            color_channels=3
        ),
        "cam2": CameraConfig(
            camera_id="cam2",
            camera_index=1,
            camera_name="Camera 2",
            resolution=ImageResolution(width=640, height=480),
            color_channels=3
        )
    }

    # Create a shared timebase mapping for all frames
    timebase_mapping = TimebaseMapping()

    # Create frame timestamps for each camera
    timestamps1 = FrameLifespanTimestamps(
        initialized_timestamp_ns=time.perf_counter_ns(),
        pre_grab_timestamp_ns=time.perf_counter_ns(),
        post_grab_timestamp_ns=time.perf_counter_ns(),
        pre_retrieve_timestamp_ns=time.perf_counter_ns(),
        post_retrieve_timestamp_ns=time.perf_counter_ns(),
        copy_to_camera_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        copy_from_camera_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        put_into_multi_frame_payload=time.perf_counter_ns(),
        copy_to_multi_frame_escape_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        copy_from_multi_frame_escape_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        start_compress_to_jpeg_timestamp_ns=time.perf_counter_ns(),
        end_compress_to_jpeg_timestamp_ns=time.perf_counter_ns(),
        start_annotation_timestamp_ns=time.perf_counter_ns(),
        end_annotation_timestamp_ns=time.perf_counter_ns()
    )

    # Create a slight delay for the second camera
    time.sleep(0.01)

    timestamps2 = FrameLifespanTimestamps(
        initialized_timestamp_ns=time.perf_counter_ns(),
        pre_grab_timestamp_ns=time.perf_counter_ns(),
        post_grab_timestamp_ns=time.perf_counter_ns(),
        pre_retrieve_timestamp_ns=time.perf_counter_ns(),
        post_retrieve_timestamp_ns=time.perf_counter_ns(),
        copy_to_camera_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        copy_from_camera_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        put_into_multi_frame_payload=time.perf_counter_ns(),
        copy_to_multi_frame_escape_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        copy_from_multi_frame_escape_shm_buffer_timestamp_ns=time.perf_counter_ns(),
        start_compress_to_jpeg_timestamp_ns=time.perf_counter_ns(),
        end_compress_to_jpeg_timestamp_ns=time.perf_counter_ns(),
        start_annotation_timestamp_ns=time.perf_counter_ns(),
        end_annotation_timestamp_ns=time.perf_counter_ns()
    )

    # Create frame metadata for each camera
    _frame_number = 1
    metadata1 = FrameMetadata(
        frame_number=_frame_number,
        camera_config=_camera_configs["cam1"],
        timestamps=timestamps1,
        timebase_mapping=timebase_mapping
    )

    metadata2 = FrameMetadata(
        frame_number=_frame_number,
        camera_config=_camera_configs["cam2"],
        timestamps=timestamps2,
        timebase_mapping=timebase_mapping
    )

    # Create sample images
    image1 = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add a red rectangle to image1
    image1[100:200, 100:200, 0] = 255

    image2 = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add a green rectangle to image2
    image2[150:250, 150:250, 1] = 255

    # Create frame payloads
    frame1 = FramePayload(
        image=image1,
        frame_metadata=metadata1
    )

    frame2 = FramePayload(
        image=image2,
        frame_metadata=metadata2
    )

    print("\n=== Testing MultiFramePayload ===")

    # Create an empty multi-frame payload
    multi_frame = MultiFramePayload.create_empty(_camera_configs)
    print(f"Created empty multi-frame payload: {multi_frame}")
    print(f"Is full: {multi_frame.full}")
    print(f"Camera IDs: {multi_frame.camera_ids}")

    # Add frames to the multi-frame payload
    print("\nAdding frames to multi-frame payload...")
    multi_frame.add_frame(frame1)
    print(f"Added frame1, is full now: {multi_frame.full}")

    multi_frame.add_frame(frame2)
    print(f"Added frame2, is full now: {multi_frame.full}")

    # Get properties of the multi-frame payload
    print(f"\nMulti-frame number: {multi_frame.multi_frame_number}")
    print(f"Timestamp (ns): {multi_frame.timestamp_ns}")

    # Get a frame from the multi-frame payload
    retrieved_frame = multi_frame.get_frame("cam1")
    print(f"\nRetrieved frame for camera 'cam1':")
    print(f"  Frame number: {retrieved_frame.frame_number}")
    print(f"  Image shape: {retrieved_frame.image.shape}")

    # Convert to numpy record array and back
    print("\nConverting to numpy record array and back...")
    rec_array = multi_frame.to_numpy_record_array()
    print(f"Record array dtype: {rec_array.dtype}")

    reconstructed_multi_frame = MultiFramePayload.from_numpy_record_array(rec_array)
    print(f"Reconstructed multi-frame is full: {reconstructed_multi_frame.full}")

    # Test MultiFrameMetadata
    print("\n=== Testing MultiFrameMetadata ===")
    metadata = MultiFrameMetadata.from_multi_frame_payload(multi_frame)

    print(f"Multi-frame number: {metadata.multi_frame_number}")
    print(f"Timestamp (unix seconds, local): {metadata.timestamp_unix_seconds_local}")
    print(f"Timestamp (unix seconds, UTC): {metadata.timestamp_unix_seconds_utc}")
    print(f"Seconds since cameras connected: {metadata.seconds_since_cameras_connected}")
    print(f"Inter-camera grab range (ns): {metadata.inter_camera_grab_range_ns}")

    # Print the frame metadata for each camera
    print("\nFrame metadata for each camera:")
    for _camera_id, _frame_metadata in metadata.frame_metadatas.items():
        print(f"  Camera {_camera_id}:")
        print(f"    Frame number: {_frame_metadata.frame_number}")
        print(f"    Camera name: {_frame_metadata.camera_config.camera_name}")
