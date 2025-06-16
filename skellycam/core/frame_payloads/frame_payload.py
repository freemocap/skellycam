import numpy as np
from numpydantic import NDArray, Shape
from pydantic import BaseModel

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frame_metadata import FrameMetadata, FRAME_METADATA_DTYPE, \
    initialize_frame_metadata_rec_array
from skellycam.core.types.numpy_record_dtypes import FRAME_DTYPE
from skellycam.utilities.rotate_image import rotate_image


def create_frame_dtype(config: CameraConfig) -> FRAME_DTYPE:
    """
    Create a numpy dtype for the frame metadata based on the camera configuration.
    """
    return np.dtype([
        ('image', np.uint8, (config.resolution.height, config.resolution.width, config.color_channels)),
        ('frame_metadata', FRAME_METADATA_DTYPE)
    ], align=True)


def initialize_frame_rec_array(camera_config: CameraConfig, frame_number: int=0) -> np.recarray:
    return np.rec.array(
        (np.zeros((camera_config.resolution.height,
                   camera_config.resolution.width,
                   camera_config.color_channels), dtype=np.uint8),
         initialize_frame_metadata_rec_array(camera_config=camera_config,
                                             frame_number=frame_number)),
        dtype=create_frame_dtype(camera_config)
    )


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
