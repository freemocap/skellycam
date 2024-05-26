from typing import ClassVar, Tuple

import numpy as np
from pydantic import Field

from skellycam.models.doc_printing_base_model import DocPrintingBaseModel
from skellycam.utilities.decorators.singleton_decorator import singleton


@singleton
class _FrameMetadataModel(DocPrintingBaseModel):
    """
    A model to represent the metadata associated with a frame of image data.

    Note that this model is not intended to be used directly, but rather as a way to hold information about the metadata, which will be created as a numpy ndarray in shared memory.

    """

    CAMERA_ID: ClassVar[int] = Field(
        description="CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)"
    )
    FRAME_NUMBER: ClassVar[int] = Field(
        description="frame_number (The number of frames that have been captured by the camera since it was started)"
    )
    TIMESTAMP_NS: ClassVar[int] = Field(description="timestamp_ns (mean of pre- and post- grab timestamps)")
    PRE_GRAB_TIMESTAMP_NS: ClassVar[int] = Field(
        description="pre_grab_timestamp_ns (timestamp before calling cv2.VideoCapture.grab())"
    )
    POST_GRAB_TIMESTAMP_NS: ClassVar[int] = Field(
        description="post_grab_timestamp_ns (timestamp after calling cv2.VideoCapture.grab())"
    )
    PRE_RETRIEVE_TIMESTAMP_NS: ClassVar[int] = Field(
        description="pre_retrieve_timestamp_ns (timestamp before calling cv2.VideoCapture.retrieve())"
    )
    POST_RETRIEVE_TIMESTAMP_NS: ClassVar[int] = Field(
        description="post_retrieve_timestamp_ns (timestamp after calling cv2.VideoCapture.retrieve())"
    )
    COPY_TO_BUFFER_TIMESTAMP_NS: ClassVar[int] = Field(
        description="copy_timestamp_ns (timestamp when frame was copied to shared memory)"
    )
    COPY_FROM_BUFFER_TIMESTAMP_NS: ClassVar[int] = Field(
        description="copy_timestamp_ns (timestamp when frame was copied from shared memory)"
    )

    @property
    def number_of_elements(self) -> int:
        return len(_FrameMetadataModel.__annotations__)

    @property
    def size_in_bytes(self) -> int:
        return int(np.dtype(np.uint64).itemsize * self.number_of_elements)

    @property
    def shape(self) -> Tuple[int, ...]:
        return (self.number_of_elements,)


FRAME_METADATA_MODEL = _FrameMetadataModel()

if __name__ == "__main__":
    print(FRAME_METADATA_MODEL)
