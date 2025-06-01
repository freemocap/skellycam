from pprint import pprint
from typing import Type

import numpy as np
from pydantic import BaseModel, Field
from pydantic import ConfigDict

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types import CameraIdString
from skellycam.core.camera.config.image_rotation_types import RotationTypes
from skellycam.core.frame_payloads.frame_payload import FramePayload
from skellycam.core.frame_payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.frame_payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, FRAME_METADATA_SHAPE, \
    create_empty_frame_metadata
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFramerate
from skellycam.core.recorders.timestamps.timebase_mapping import TimeBaseMapping
from skellycam.utilities.rotate_image import rotate_image


class MultiFrameNumpyBuffer(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={
            np.ndarray: lambda v: v.tolist(),
        },
    )
    mf_time_mapping_buffer: np.ndarray
    mf_metadata_buffer: np.ndarray
    mf_image_buffer: np.ndarray
    multi_frame_number: int

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: 'MultiFramePayload') -> 'MultiFrameNumpyBuffer':
        frames = list(multi_frame_payload.frames.values())

        time_mapping_buffer = multi_frame_payload.timebase_mapping.to_numpy_buffer()

        mf_metadatas = np.concatenate([frame.metadata for frame in frames], axis=0)
        expected_metadata_shape = FRAME_METADATA_SHAPE[0] * len(frames)
        if mf_metadatas.shape[0] != expected_metadata_shape:
            raise ValueError(
                f"MultiFrameNumpyBuffer metadata buffer has the wrong shape. Should be {expected_metadata_shape} but is {mf_metadatas.shape[0]}")

        mf_images = np.concatenate([frame.image.ravel() for frame in frames], axis=0)

        mf_number = {frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value] for frame in frames}
        if len(mf_number) > 1:
            raise ValueError(f"MultiFramePayload has multiple frame numbers {mf_number}")

        return cls(
            mf_time_mapping_buffer=time_mapping_buffer,
            mf_metadata_buffer=mf_metadatas,
            mf_image_buffer=mf_images,
            multi_frame_number=mf_number.pop()
        )

    def to_multi_frame_payload(self, camera_configs: CameraConfigs) -> 'MultiFramePayload':
        time_mapping = TimeBaseMapping.from_numpy_buffer(self.mf_time_mapping_buffer)

        if self.mf_metadata_buffer.shape[0] % FRAME_METADATA_SHAPE[0] != 0:
            raise ValueError(
                f"MultiFrameNumpyBuffer metadata buffer has the wrong shape. Should be a multiple of {FRAME_METADATA_SHAPE[0]} but is {self.mf_metadata_buffer.shape[0]}"
            )

        number_of_cameras = self.mf_metadata_buffer.shape[0] // FRAME_METADATA_SHAPE[0]
        mf_metadatas = np.split(self.mf_metadata_buffer, number_of_cameras)
        frames = {}
        buffer_index = 0

        for metadata in mf_metadatas:
            if not metadata.shape == FRAME_METADATA_SHAPE:
                raise ValueError(
                    f"Metadata shape {metadata.shape} does not match expected shape {FRAME_METADATA_SHAPE}"
                )
            if metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value] != self.multi_frame_number:
                raise ValueError(
                    f"Metadata frame number {metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} does not match expected frame number {self.multi_frame_number}"
                )
            camera_index = metadata[FRAME_METADATA_MODEL.CAMERA_INDEX.value]
            camera_id = camera_index_to_camera_id(camera_index=camera_index,
                                                  camera_configs=camera_configs)

            image_shape = (metadata[FRAME_METADATA_MODEL.IMAGE_HEIGHT.value],
                           metadata[FRAME_METADATA_MODEL.IMAGE_WIDTH.value],
                           metadata[FRAME_METADATA_MODEL.IMAGE_COLOR_CHANNELS.value])

            if camera_configs[camera_id].image_shape != image_shape:
                raise ValueError(
                    f"Camera config image shape {camera_configs[camera_id].image_shape} does not match image shape {image_shape}"
                )

            image_length = np.prod(image_shape)
            image_buffer = self.mf_image_buffer[int(buffer_index):int(buffer_index + image_length)]
            buffer_index += image_length
            image = image_buffer.reshape(image_shape)
            frames[camera_id] = FramePayload(metadata=metadata, image=image)

        return MultiFramePayload(
            frames=frames,
            camera_configs=camera_configs,
            timebase_mapping=time_mapping
        )

    @classmethod
    def from_buffers(cls: Type['MultiFrameNumpyBuffer'],
                     mf_time_mapping_buffer: np.ndarray,
                     mf_metadata_buffer: np.ndarray,
                     mf_image_buffer: np.ndarray) -> 'MultiFrameNumpyBuffer':
        reshaped_metadata = mf_metadata_buffer.reshape(-1, FRAME_METADATA_SHAPE[0])
        frame_numbers = np.unique(reshaped_metadata[:, FRAME_METADATA_MODEL.FRAME_NUMBER.value])

        if len(frame_numbers) > 1:
            raise ValueError(f"MultiFramePayload has multiple frame numbers {frame_numbers}")

        return cls(
            mf_time_mapping_buffer=mf_time_mapping_buffer,
            mf_metadata_buffer=mf_metadata_buffer,
            mf_image_buffer=mf_image_buffer,
            multi_frame_number=int(frame_numbers[0])
        )

    def __str__(self):
        return f"MultiFrameNumpyBuffer: metadata shape {self.mf_metadata_buffer.shape}, image shape {self.mf_image_buffer.shape}, time mapping shape {self.mf_time_mapping_buffer.shape}"


class MultiFramePayload(BaseModel):
    frames: dict[CameraIdString, FramePayload | None]
    timebase_mapping: TimeBaseMapping = Field(default_factory=TimeBaseMapping, description=TimeBaseMapping.__doc__)
    backend_framerate: CurrentFramerate | None = None
    frontend_framerate: CurrentFramerate | None = None
    camera_configs: CameraConfigs

    @classmethod
    def create_initial(cls, camera_configs: CameraConfigs) -> 'MultiFramePayload':
        return cls(frames={camera_id: None for camera_id in camera_configs.keys()},
                   camera_configs=camera_configs, )

    @classmethod
    def from_previous(cls,
                      previous: 'MultiFramePayload',
                      camera_configs: CameraConfigs) -> 'MultiFramePayload':
        return cls(frames={camera_id: None for camera_id in previous.frames.keys()},
                   timebase_mapping=previous.timebase_mapping,
                   camera_configs=camera_configs,
                   )

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
        frame_numbers = [frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value] for frame in self.frames.values()]
        mf_number = set(frame_numbers)
        if len(mf_number) > 1:
            raise ValueError(f"MultiFramePayload has multiple frame numbers {mf_number}")
        return mf_number.pop()

    def to_numpy_buffer(self) -> MultiFrameNumpyBuffer:
        return MultiFrameNumpyBuffer.from_multi_frame_payload(self)

    @classmethod
    def from_numpy_buffer(cls, buffer: MultiFrameNumpyBuffer, camera_configs: CameraConfigs) -> 'MultiFramePayload':
        return buffer.to_multi_frame_payload(camera_configs=camera_configs)

    def add_frame(self, frame_dto: FramePayload) -> None:
        camera_index = frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_INDEX.value]
        camera_id = camera_index_to_camera_id(camera_index=camera_index,
                                              camera_configs=self.camera_configs)
        for frame in self.frames.values():
            if frame:
                if frame.metadata[FRAME_METADATA_MODEL.CAMERA_INDEX.value] == camera_index:
                    raise ValueError(
                        f"Cannot add frame for camera_id {camera_id} to MultiFramePayloadDTO, frame already exists!")
                if not frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value] == frame_dto.metadata[
                    FRAME_METADATA_MODEL.FRAME_NUMBER.value]:
                    raise ValueError(
                        f"Cannot add frame for camera_id {camera_id} to MultiFramePayloadDTO, frame number mismatch!")
        self.frames[camera_id] = frame_dto

    def get_frame(self, camera_id: CameraIdString, rotate: bool = True,
                  return_copy: bool = True) -> FramePayload | None:

        if return_copy:
            frame = self.frames[camera_id].model_copy()
        else:
            frame = self.frames[camera_id]

        if frame is None:
            raise ValueError(f"Cannot get frame for camera_id {camera_id} from MultiFramePayloadDTO, frame is None")

        if rotate and not self.camera_configs[camera_id].rotation == RotationTypes.NO_ROTATION:
            frame.image = rotate_image(frame.image, self.camera_configs[camera_id].rotation)

        return frame

    def to_metadata(self) -> 'MultiFrameMetadata':
        return MultiFrameMetadata.from_multi_frame_payload(multi_frame_payload=self)

    def __str__(self) -> str:
        print_str = f"["
        for camera_id, frame in self.frames.items():
            print_str += str(frame) + "\n"
        print_str += "]"
        return print_str


class MultiFrameMetadata(BaseModel):
    multi_frame_number: int
    frame_metadatas: dict[CameraIdString, FrameMetadata]
    timebase_mapping: TimeBaseMapping

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload):
        return cls(
            multi_frame_number=multi_frame_payload.multi_frame_number,
            frame_metadatas={
                camera_id: FrameMetadata.from_frame_metadata_array(frame.metadata)
                for camera_id, frame in multi_frame_payload.frames.items()
            },
            timebase_mapping=multi_frame_payload.timebase_mapping
        )

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.frame_metadatas.keys())

    @property
    def timestamp_unix_seconds_local(self) -> float:
        mean_frame_grab_ns = np.mean([
            frame_metadata.frame_lifespan_timestamps.post_grab_timestamp_ns
            for frame_metadata in self.frame_metadatas.values()
        ])
        unix_ns = self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(int(mean_frame_grab_ns), local_time=True)
        return unix_ns / 1e9
    @property
    def timestamp_unix_seconds_utc(self) -> float:
        mean_frame_grab_ns = np.mean([
            frame_metadata.frame_lifespan_timestamps.post_grab_timestamp_ns
            for frame_metadata in self.frame_metadatas.values()
        ])
        unix_ns = self.timebase_mapping.convert_perf_counter_ns_to_unix_ns(int(mean_frame_grab_ns), local_time=False)
        return unix_ns / 1e9

    @property
    def seconds_since_cameras_connected(self) -> float:
        return self.timestamp_unix_seconds_utc - self.timebase_mapping.utc_time_ns / 1e9

    @property
    def intercamera_grab_range_ns(self) -> int:
        grab_times = [frame_metadata.frame_lifespan_timestamps.post_grab_timestamp_ns
                      for frame_metadata in self.frame_metadatas.values()]
        return int(np.max(grab_times) - np.min(grab_times))



def camera_index_to_camera_id(camera_index: int, camera_configs: CameraConfigs) -> CameraIdString:
    for camera_id, camera_config in camera_configs.items():
        if camera_config.camera_index == camera_index:
            return camera_id
    raise ValueError(f"Camera index {camera_index} not found in camera configs")


if __name__ == "__main__":
    def create_example_multi_frame_payload() -> MultiFramePayload:
        camera_configs = {CameraIdString(id): CameraConfig(camera_index=id) for id in range(3)}
        multi_frame_payload = MultiFramePayload.create_initial(camera_configs=camera_configs)
        for camera_id in camera_configs.keys():
            frame_metadata = create_empty_frame_metadata(config=camera_configs[camera_id], frame_number=0)
            frame_payload = FramePayload(metadata=frame_metadata,
                                         image=np.random.randint(0, 255, camera_configs[camera_id].image_shape,
                                                                 dtype=np.uint8))
            multi_frame_payload.add_frame(frame_payload)
        return multi_frame_payload


    og_mf = create_example_multi_frame_payload()
    print(og_mf)
    buffer = og_mf.to_numpy_buffer()
    print(buffer)
    new_mf = MultiFramePayload.from_numpy_buffer(
        buffer=MultiFrameNumpyBuffer.from_buffers(mf_time_mapping_buffer=buffer.mf_time_mapping_buffer,
                                                  mf_metadata_buffer=buffer.mf_metadata_buffer,
                                                  mf_image_buffer=buffer.mf_image_buffer),
        camera_configs=og_mf.camera_configs)
    for _camera_id in og_mf.camera_ids:
        og_frame = og_mf.get_frame(_camera_id)
        new_frame = new_mf.get_frame(_camera_id)
        if not np.array_equal(og_frame.image, new_frame.image):
            raise ValueError(f"Images for camera_id {_camera_id} do not match")
        if not np.array_equal(og_frame.metadata, new_frame.metadata):
            raise ValueError(f"Metadata for camera_id {_camera_id} do not match")
    print(new_mf)

    print("Metadata:")
    pprint(og_mf.to_metadata())
