import logging

import numpy as np

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.ipc.shared_memory.ring_buffer_shared_memory import SharedMemoryRingBuffer
from skellycam.core.types.frame_dtype_factories import create_frame_dtype

logger = logging.getLogger(__name__)


class CameraSharedMemoryRingBuffer(SharedMemoryRingBuffer):

    @property
    def latest_frame_number(self) -> int:
        if not self.valid:
            raise ValueError("Shared memory is not valid!")
        return self.last_written_index.value

    @classmethod
    def from_config(cls,
                    camera_config: CameraConfig,
                    timebase_mapping: TimebaseMapping,
                    read_only: bool = False):
        # Create a dummy frame record array for shape and dtype
        frame_dtype = create_frame_dtype(camera_config)
        dummy_frame = np.recarray(1, dtype=frame_dtype)

        # Initialize the frame metadata
        dummy_frame.frame_metadata.camera_info = camera_config.to_frame_camera_info()[0]
        dummy_frame.frame_metadata.frame_number = -99
        dummy_frame.frame_metadata.timebase_mapping = timebase_mapping.to_numpy_record_array()[0]

        # Initialize the image with zeros
        image_shape = (camera_config.resolution.height, camera_config.resolution.width, camera_config.color_channels)
        dummy_frame.image[0] = np.zeros(image_shape, dtype=np.uint8)

        return cls.create(
            example_data=dummy_frame,
            read_only=read_only,
        )

    @property
    def new_frame_available(self):
        return self.new_data_available

    def put_frame(self, frame_rec_array: np.recarray, overwrite: bool):
        if self.read_only:
            raise ValueError("Cannot put new frame into read-only instance of shared memory!")
        self.put_data(frame_rec_array, overwrite_allowed=overwrite)

    def frame_slot(self, frame_number: int) -> np.ndarray:
        """Writable one-record view of the ring slot for `frame_number`, a structured array (fields by name).

        Ring index and frame number are the same (readers fetch frame N at index N), so a writer that
        skips frame numbers writes each frame at its own number, then publishes it with `commit_frame`.
        A plain structured view keeps field access in numpy's C code: recarray attributes run in Python.
        """
        if self.read_only:
            raise ValueError("Cannot write into a read-only instance of shared memory!")
        slots = getattr(self, "_writable_slots", None)
        if slots is None:
            slots = self._writable_slots = self.ring_shm.buffer.view(np.ndarray)
        slot = frame_number % self.ring_buffer_length
        return slots[slot:slot + 1]

    def commit_frame(self, frame_number: int) -> None:
        """Publish the frame written into `frame_slot(frame_number)` as this camera's newest frame.

        This instance is the ring's only writer, so it checks frame order against its own last commit.
        """
        last = getattr(self, "_last_committed", None)
        if last is None:
            last = self.last_written_index.value
        if frame_number <= last:
            raise ValueError(f"Frame {frame_number} is not newer than frame {last}")
        self.last_written_index.value = frame_number
        self._last_committed = frame_number

    def retrieve_latest_frame(self, frame_rec_array:np.recarray) -> np.recarray:
        frame_rec_array = self.get_latest_data(frame_rec_array)
        return frame_rec_array

    def retrieve_next_frame(self, frame_rec_array:np.recarray) -> np.recarray:
        frame_rec_array = self.get_next_data(frame_rec_array)
        return frame_rec_array
