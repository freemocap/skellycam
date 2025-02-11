from pprint import pprint
from typing import Dict, Optional, List, Type

import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from skellycam.core import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes
from skellycam.core.frames.payloads.frame_payload import FramePayload
from skellycam.core.frames.payloads.metadata.frame_metadata import FrameMetadata
from skellycam.core.frames.payloads.metadata.frame_metadata_enum import FRAME_METADATA_MODEL, FRAME_METADATA_SHAPE, \
    create_empty_frame_metadata
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFramerate
from skellycam.core.recorders.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping
from skellycam.utilities.rotate_image import rotate_image


class MultiFrameNumpyBuffer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    mf_time_mapping_buffer: np.ndarray
    mf_metadata_buffer: np.ndarray
    mf_image_buffer: np.ndarray
    multi_frame_number: int


    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: 'MultiFramePayload') -> 'MultiFrameNumpyBuffer':
        frames = list(multi_frame_payload.frames.values())

        time_mapping_buffer = multi_frame_payload.utc_ns_to_perf_ns.to_numpy_buffer()

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
        time_mapping = UtcToPerfCounterMapping.from_numpy_buffer(self.mf_time_mapping_buffer)

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

            image_shape = (metadata[FRAME_METADATA_MODEL.IMAGE_HEIGHT.value],
                           metadata[FRAME_METADATA_MODEL.IMAGE_WIDTH.value],
                           metadata[FRAME_METADATA_MODEL.IMAGE_COLOR_CHANNELS.value])

            if camera_configs[metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]].image_shape != image_shape:
                raise ValueError(
                    f"Camera config image shape {camera_configs[metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]].image_shape} does not match image shape {image_shape}"
                )

            image_length = np.prod(image_shape)
            image_buffer = self.mf_image_buffer[int(buffer_index):int(buffer_index + image_length)]
            buffer_index += image_length
            image = image_buffer.reshape(image_shape)
            frames[metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]] = FramePayload(metadata=metadata, image=image)

        return MultiFramePayload(
            frames=frames,
            camera_configs=camera_configs,
            utc_ns_to_perf_ns=time_mapping
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
            multi_frame_number=frame_numbers[0]
        )
    # @classmethod
    # def from_multi_frame_payload(cls, multi_frame_payload: 'MultiFramePayload') -> 'MultiFrameNumpyBuffer':
    #     time_mapping_buffer = multi_frame_payload.utc_ns_to_perf_ns.to_numpy_buffer()
    #
    #     mf_metadatas = [frame.metadata for frame in multi_frame_payload.frames.values()]
    #     mf_metadata_buffer = np.concatenate(mf_metadatas, axis=0)
    #     if mf_metadata_buffer.shape[0] != FRAME_METADATA_SHAPE[0] * len(multi_frame_payload.frames):
    #         raise ValueError(
    #             f"MultiFrameNumpyBuffer metadata buffer has the wrong shape. Should be {FRAME_METADATA_SHAPE[0] * len(multi_frame_payload.frames)} but is {mf_metadata_buffer.shape[0]}")
    #
    #     mf_images = [frame.image for frame in multi_frame_payload.frames.values()]
    #     mf_images_ravelled = [image.ravel() for image in mf_images]
    #     mf_image_buffer = np.concatenate(mf_images_ravelled, axis=0)
    #
    #     mf_number = [frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value] for frame in
    #                  multi_frame_payload.frames.values()]
    #     if len(set(mf_number)) > 1:
    #         raise ValueError(f"MultiFramePayload has multiple frame numbers {set(mf_number)}")
    #
    #     return cls(mf_time_mapping_buffer=time_mapping_buffer,
    #                mf_metadata_buffer=mf_metadata_buffer,
    #                mf_image_buffer=mf_image_buffer,
    #                multi_frame_number=mf_number.pop())
    #
    # @classmethod
    # def from_buffers(cls,
    #                  mf_time_mapping_buffer: np.ndarray,
    #                  mf_metadata_buffer: np.ndarray,
    #                  mf_image_buffer: np.ndarray) -> 'MultiFrameNumpyBuffer':
    #     frame_numbers = set(mf_metadata_buffer.reshape(-1, FRAME_METADATA_SHAPE[0])[:, FRAME_METADATA_MODEL.FRAME_NUMBER.value])
    #
    #     if len(set(frame_numbers)) > 1:
    #         raise ValueError(f"MultiFramePayload has multiple frame numbers {set(frame_numbers)}")
    #     return cls(mf_time_mapping_buffer=mf_time_mapping_buffer,
    #                mf_metadata_buffer=mf_metadata_buffer,
    #                mf_image_buffer=mf_image_buffer,
    #                multi_frame_number=frame_numbers.pop())
    #
    # def to_multi_frame_payload(self, camera_configs: CameraConfigs) -> 'MultiFramePayload':
    #
    #     time_mapping = UtcToPerfCounterMapping.from_numpy_buffer(self.mf_time_mapping_buffer)
    #
    #     if self.mf_metadata_buffer.shape[0] % FRAME_METADATA_SHAPE[0] != 0:
    #         raise ValueError(
    #             f"MultiFrameNumpyBuffer metadata buffer has the wrong shape. Should be a multiple of {FRAME_METADATA_SHAPE[0]} but is {self.mf_metadata_buffer.shape[0]}")
    #     number_of_cameras = self.mf_metadata_buffer.shape[0] // FRAME_METADATA_SHAPE[0]
    #     mf_metadatas = np.split(self.mf_metadata_buffer, number_of_cameras)
    #     frames = {}
    #     for metadata in mf_metadatas:
    #         if not metadata.shape == FRAME_METADATA_SHAPE:
    #             raise ValueError(
    #                 f"Metadata shape {metadata.shape} does not match expected shape {FRAME_METADATA_SHAPE}")
    #         if not metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value] == self.multi_frame_number:
    #             raise ValueError(
    #                 f"Metadata frame number {metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value]} does not match expected frame number {self.multi_frame_number}")
    #         camera_id = CameraId(metadata[FRAME_METADATA_MODEL.CAMERA_ID.value])
    #         image_width = metadata[FRAME_METADATA_MODEL.IMAGE_WIDTH.value]
    #         image_height = metadata[FRAME_METADATA_MODEL.IMAGE_HEIGHT.value]
    #         image_color_channels = metadata[FRAME_METADATA_MODEL.IMAGE_COLOR_CHANNELS.value]
    #         image_shape = (image_height, image_width, image_color_channels)
    #         if camera_configs[camera_id].image_shape != image_shape:
    #             raise ValueError(
    #                 f"Camera config image shape {camera_configs[camera_id].image_shape} does not match image shape {image_shape}")
    #         image_length = np.prod(image_shape)
    #         image_buffer = self.mf_image_buffer[:image_length]
    #         self.mf_image_buffer = self.mf_image_buffer[image_length:]
    #         image = image_buffer.reshape(image_shape)
    #         frames[camera_id] = FramePayload(metadata=metadata, image=image)
    #     return MultiFramePayload(frames=frames,
    #                              camera_configs=camera_configs,
    #                              utc_ns_to_perf_ns=time_mapping)

    def __str__(self):
        return f"MultiFrameNumpyBuffer: metadata shape {self.mf_metadata_buffer.shape}, image shape {self.mf_image_buffer.shape}, time mapping shape {self.mf_time_mapping_buffer.shape}"


class MultiFramePayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    frames: Dict[CameraId, Optional[FramePayload]]
    utc_ns_to_perf_ns: UtcToPerfCounterMapping = Field(default_factory=UtcToPerfCounterMapping,
                                                       description=UtcToPerfCounterMapping.__doc__)
    backend_framerate: CurrentFramerate|None = None
    frontend_framerate: CurrentFramerate|None = None
    camera_configs: CameraConfigs

    @classmethod
    def create_initial(cls, camera_configs: CameraConfigs) -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in camera_configs.keys()},
                   camera_configs=camera_configs, )

    @classmethod
    def from_previous(cls,
                      previous: 'MultiFramePayload',
                      camera_configs: CameraConfigs) -> 'MultiFramePayload':
        return cls(frames={CameraId(camera_id): None for camera_id in previous.frames.keys()},
                   utc_ns_to_perf_ns=previous.utc_ns_to_perf_ns,
                   camera_configs=camera_configs,
                   )

    @property
    def full(self) -> bool:
        return all([frame is not None for frame in self.frames.values()])

    @property
    def camera_ids(self) -> List[CameraId]:
        return list(self.frames.keys())

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
        camera_id = frame_dto.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value]
        for frame in self.frames.values():
            if frame:
                if frame.metadata[FRAME_METADATA_MODEL.CAMERA_ID.value] == camera_id:
                    raise ValueError(
                        f"Cannot add frame for camera_id {camera_id} to MultiFramePayloadDTO, frame already exists!")
                if not frame.metadata[FRAME_METADATA_MODEL.FRAME_NUMBER.value] == frame_dto.metadata[
                    FRAME_METADATA_MODEL.FRAME_NUMBER.value]:
                    raise ValueError(
                        f"Cannot add frame for camera_id {camera_id} to MultiFramePayloadDTO, frame number mismatch!")
        self.frames[camera_id] = frame_dto

    def get_frame(self, camera_id: CameraId, rotate: bool = True, return_copy: bool = True) -> Optional[FramePayload]:

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
    frame_number: int
    frame_metadata_by_camera: Dict[CameraId, FrameMetadata]
    utc_ns_to_perf_ns: UtcToPerfCounterMapping

    @classmethod
    def from_multi_frame_payload(cls, multi_frame_payload: MultiFramePayload):
        return cls(
            frame_number=multi_frame_payload.multi_frame_number,
            frame_metadata_by_camera={
                camera_id: FrameMetadata.from_frame_metadata_array(frame.metadata)
                for camera_id, frame in multi_frame_payload.frames.items()
            },
            utc_ns_to_perf_ns=multi_frame_payload.utc_ns_to_perf_ns
        )

    @property
    def timestamp_unix_seconds(self) -> float:
        mean_frame_grab_ns = np.mean([
            frame_metadata.frame_lifespan_timestamps_ns.post_grab_timestamp_ns
            for frame_metadata in self.frame_metadata_by_camera.values()
        ])
        unix_ns = self.utc_ns_to_perf_ns.convert_perf_counter_ns_to_unix_ns(mean_frame_grab_ns)
        return unix_ns / 1e9

    @property
    def seconds_since_cameras_connected(self) -> float:
        return self.timestamp_unix_seconds - self.utc_ns_to_perf_ns.utc_time_ns / 1e9

    def to_df_row(self):
        row = {
            "multi_frame_number": self.frame_number,
            "seconds_since_cameras_connected": self.seconds_since_cameras_connected,
            "timestamp_unix_seconds": self.timestamp_unix_seconds,
        }
        for camera_id, frame_metadata in self.frame_metadata_by_camera.items():
            row.update(**frame_metadata.to_df_row())
        return row

def create_example_multi_frame_payload() -> MultiFramePayload:
    camera_configs = {CameraId(id): CameraConfig(camera_id=id) for id in range(3)}
    multi_frame_payload = MultiFramePayload.create_initial(camera_configs=camera_configs)
    for camera_id in camera_configs.keys():
        frame_metadata = create_empty_frame_metadata(camera_id=camera_id, frame_number=0,
                                                     config=camera_configs[camera_id])
        frame_payload = FramePayload(metadata=frame_metadata,
                                     image=np.random.randint(0, 255, camera_configs[camera_id].image_shape,
                                                             dtype=np.uint8))
        multi_frame_payload.add_frame(frame_payload)
    return multi_frame_payload


if __name__ == "__main__":
    og_mf = create_example_multi_frame_payload()
    print(og_mf)
    buffer = og_mf.to_numpy_buffer()
    print(buffer)
    new_mf = MultiFramePayload.from_numpy_buffer(buffer=MultiFrameNumpyBuffer.from_buffers(mf_time_mapping_buffer=buffer.mf_time_mapping_buffer,
                                                                                           mf_metadata_buffer=buffer.mf_metadata_buffer,
                                                                                           mf_image_buffer=buffer.mf_image_buffer),
                                                 camera_configs=og_mf.camera_configs)
    for camera_id in og_mf.camera_ids:
        og_frame = og_mf.get_frame(camera_id)
        new_frame = new_mf.get_frame(camera_id)
        if not np.array_equal(og_frame.image, new_frame.image):
            raise ValueError(f"Images for camera_id {camera_id} do not match")
        if not np.array_equal(og_frame.metadata, new_frame.metadata):
            raise ValueError(f"Metadata for camera_id {camera_id} do not match")
    print(new_mf)

    print("Metadata:")
    pprint(og_mf.to_metadata())