import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata, initialize_frame_metadata_rec_array
from skellycam.core.recorders.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.numpy_record_dtypes import create_frame_dtype
from skellycam.utilities.rotate_image import rotate_image


# skellycam/core/frame_payloads/frame_payload.py
def initialize_frame_rec_array(camera_config: CameraConfig,
                               timebase_mapping: TimebaseMapping,
                               frame_number: int = 0) -> np.recarray:
    """
    Create a frame record array with the correct shape and dtype.

    The issue was that np.rec.array was being called with arrays of different shapes:
    - The image array had shape (height, width, channels)
    - The metadata array had shape (1,)

    This fix creates a record array with the correct dtype and then assigns values to it.
    """
    # Create the record array with the correct dtype
    dtype = create_frame_dtype(camera_config)
    result = np.recarray(1, dtype=dtype)

    # Create the image array
    image_array = np.ones((camera_config.resolution.height,
                            camera_config.resolution.width,
                            camera_config.color_channels), dtype=np.uint8) + camera_config.camera_index

    # Get the metadata array
    metadata_array = initialize_frame_metadata_rec_array(camera_config=camera_config,
                                                         frame_number=frame_number,
                                                         timebase_mapping=timebase_mapping)

    # Assign values to the record array
    result.image[0] = image_array
    result.frame_metadata[0] = metadata_array[0]

    return result

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
        return self.frame_metadata.timestamp_ns

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
    def from_numpy_record_array(cls, array: np.recarray):
        if array.dtype != create_frame_dtype(CameraConfig.from_numpy_record_array(array.frame_metadata.camera_config)):
            raise ValueError(f"FramePayload array shape mismatch - "
                             f"Expected: {create_frame_dtype(CameraConfig.from_numpy_record_array(array.frame_metadata.camera_config))}, "
                             f"Actual: {array.dtype}")

        frame =  cls(
            image=array.image,
            frame_metadata=FrameMetadata.from_numpy_record_array(array.frame_metadata)
        )
        frame.image = rotate_image(frame.image, frame.camera_config.rotation)
        return frame

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
