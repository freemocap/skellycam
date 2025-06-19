import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import create_frame_dtype
from skellycam.utilities.rotate_image import rotate_image




class FramePayload(BaseModel):
    image: NDArray[Shape["* image_height, * image_width, * color_channels"], np.uint8]
    frame_metadata: FrameMetadata

    @property
    def camera_id(self):
        return self.frame_metadata.camera_id

    @property
    def frame_number(self):
        return self.frame_metadata.frame_number

    @property
    def timestamp_ns(self) -> int:
        """
        De facto timestamp for this frame is defined as the average of the pre-grab and post-grab timestamps (i.e. the hypothetical moment the image was grabbed).
        """
        return self.frame_metadata.timestamps.post_grab_ns

    @property
    def height(self):
        return self.image.shape[0]

    @property
    def width(self):
        return self.image.shape[1]

    @property
    def camera_config(self) -> CameraConfig:
        return self.frame_metadata.camera_config

    @classmethod
    def create_initial(cls, camera_config: CameraConfig, timebase_mapping:TimebaseMapping) -> "FramePayload":
        """
        Create a dummy FramePayload with a dummy image and metadata.
        """
        image_shape = (camera_config.resolution.height, camera_config.resolution.width, camera_config.color_channels)
        dummy_image = np.ones(image_shape, dtype=np.uint8) + camera_config.camera_index

        frame_metadata = FrameMetadata.create_initial(camera_config=camera_config, timebase_mapping=timebase_mapping)

        return cls(image=dummy_image, frame_metadata=frame_metadata)
    @classmethod
    def create_dummy(cls, camera_config: CameraConfig) -> "FramePayload":
        """
        Create a dummy FramePayload with a dummy image and metadata, for shape and size inference.
        """
        image_shape = (camera_config.resolution.height, camera_config.resolution.width, camera_config.color_channels)
        dummy_image = np.ones(image_shape, dtype=np.uint8) + camera_config.camera_index

        frame_metadata = FrameMetadata.create_initial(camera_config=camera_config, timebase_mapping=TimebaseMapping())

        return cls(image=dummy_image, frame_metadata=frame_metadata)

    @classmethod
    def create_from_numpy_record_array(cls, array: np.recarray, apply_config_rotation: bool=False):
        if array.dtype != create_frame_dtype(CameraConfig.from_numpy_record_array(array.frame_metadata.camera_config)):
            raise ValueError(f"FramePayload array shape mismatch - "
                             f"Expected: {create_frame_dtype(CameraConfig.from_numpy_record_array(array.frame_metadata.camera_config))}, "
                             f"Actual: {array.dtype}")

        frame =  cls(
            image=array.image,
            frame_metadata=FrameMetadata.from_numpy_record_array(array.frame_metadata)
        )
        if apply_config_rotation:
            frame.image = rotate_image(frame.image, frame.camera_config.rotation)
        return frame
    def update_from_numpy_record_array(self, array: np.recarray, apply_config_rotation: bool=False):
        """
        Update the FramePayload from a numpy record array.
        """
        if array.dtype != create_frame_dtype(self.frame_metadata.camera_config):
            raise ValueError(f"FramePayload array shape mismatch - "
                             f"Expected: {create_frame_dtype(self.frame_metadata.camera_config)}, "
                             f"Actual: {array.dtype}")
        if self.frame_metadata.timestamps.timebase_mapping.to_numpy_record_array() != array.frame_metadata.timestamps.timebase_mapping:
            raise ValueError(f"FramePayload timebase mapping mismatch - "
                             f"Expected: {self.frame_metadata.timestamps.timebase_mapping}, "
                             f"Actual: {array.frame_metadata.timestamps.timebase_mapping}")

        self.image = array.image
        self.frame_metadata = FrameMetadata.from_numpy_record_array(array.frame_metadata)

        if apply_config_rotation:
            self.image = rotate_image(self.image, self.camera_config.rotation)
    def to_numpy_record_array(self) -> np.recarray:
        """
        Convert the FramePayload to a numpy record array.
        """
        # Create a record array with the correct shape (1,)
        result = np.recarray(1, dtype=create_frame_dtype(self.frame_metadata.camera_config))

        # Assign values to the record array
        result.image[0] = self.image
        result.frame_metadata[0] = self.frame_metadata.to_numpy_record_array()[0]

        return result


    def __str__(self):
        print_str = (
            f"Camera {self.camera_id}: Image shape: {self.image.shape}, "
        )
        return print_str
