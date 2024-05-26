from typing import ClassVar

import numpy as np
from pydantic import Field

from skellycam.models.doc_printing_base_model import DocPrintingBaseModel


class _FrameMetadataModel(DocPrintingBaseModel):
    """
    A model to represent the metadata associated with a frame of image data.

    Note that this model is not intended to be used directly, but rather as a way to hold information about the metadata, which will be created as a numpy ndarray in shared memory.

    """
    CAMERA_ID: ClassVar[int] = Field(1,
                                     description="CameraId (as an int corresponding the int used to create the cv2.VideoCapture object)")
    FRAME_NUMBER: ClassVar[int] = Field(2,
                                        description="frame_number (The number of frames that have been captured by the camera since it was started)")
    TIMESTAMP_NS: ClassVar[int] = Field(3, description="timestamp_ns (mean of pre- and post- grab timestamps)")
    PRE_GRAB_TIMESTAMP_NS: ClassVar[int] = Field(4,
                                                 description="pre_grab_timestamp_ns (timestamp before calling cv2.VideoCapture.grab())")
    POST_GRAB_TIMESTAMP_NS: ClassVar[int] = Field(5,
                                                  description="post_grab_timestamp_ns (timestamp after calling cv2.VideoCapture.grab())")
    PRE_RETRIEVE_TIMESTAMP_NS: ClassVar[int] = Field(6,
                                                     description="pre_retrieve_timestamp_ns (timestamp before calling cv2.VideoCapture.retrieve())")
    POST_RETRIEVE_TIMESTAMP_NS: ClassVar[int] = Field(7,
                                                      description="post_retrieve_timestamp_ns (timestamp after calling cv2.VideoCapture.retrieve())")
    COPY_TIMESTAMP_NS: ClassVar[int] = Field(8,
                                             description="copy_timestamp_ns (timestamp when frame was copied to shared memory)")

    @property
    def number_of_elements(self) -> int:
        return len(_FrameMetadataModel.__annotations__)

    @property
    def size_in_bytes(self) -> int:
        return np.dtype(np.uint64).itemsize * self.frame_metadata_elements


FRAME_METADATA_MODEL = _FrameMetadataModel()

if __name__ == "__main__":
    print(FRAME_METADATA_MODEL)
