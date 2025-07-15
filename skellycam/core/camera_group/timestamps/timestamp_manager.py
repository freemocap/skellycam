import logging

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from skellycam.core.camera_group.timestamps.recording_timestamps import RecordingTimestamps
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString


logger = logging.getLogger(__name__)
def find_earliest_frame_metadata(frame_metadatas: dict[CameraIdString, np.recarray]) -> int:

    if len(frame_metadatas) == 0:
        raise ValueError("The multiframe record array is empty.")
    ts = []
    for metadata in frame_metadatas.values():
        ts.append(metadata.timestamps.pre_frame_grab_ns)
    if len(ts) == 0:
        raise ValueError("No metadata found in the multiframe record array.")
    return int(np.min(ts))

class TimestampManager(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mf_metadatas: list[dict[CameraIdString, np.recarray]] = Field(
        default_factory=list,
        description="List of dictionaries mapping camera IDs to their respective frame timestamps - list index == frame number (within recording). "
                    "Stored as recarrays during recording and converted to MultiFrameTimestamps after recording is complete (Pydantic validation is relatively slow!).")
    recording_start_ns: int | None = Field(
        default=None,
        description="The timestamp of the earliest 'grab' timestamp from the frames in the first multiframe of this recording, in nanoseconds. "
                    "This is as the Zero timebase to calculate relative timestamps for each multiframe payload.")

    @property
    def anything_recorded(self) -> bool:
        return self.recording_start_ns is not None

    def add_mf_metadatas(self, mf_metadatas: list[dict[CameraIdString, np.recarray]]):
        if len(mf_metadatas) == 0:
            return
        if self.recording_start_ns is None:
            # set recording start time to the earliest camera's first timestamp on the first multiframe
            self.recording_start_ns = find_earliest_frame_metadata(mf_metadatas[0])

        self.mf_metadatas.extend(mf_metadatas)

    def save_timestamps(self, recording_info: RecordingInfo):
        """
        Saves the timestamps to a CSV file in the recording info's timestamps folder.
        The file is named with the recording name and has a .csv extension.
        """
        if not self.anything_recorded:
            raise ValueError("No timestamps recorded. Cannot save timestamps.")
        recording_timestamps = RecordingTimestamps.from_camera_timestamps(
            recording_start_ns=self.recording_start_ns,
            recording_info=recording_info,
            mf_metadatas=self.mf_metadatas
        )

        recording_timestamps.save_timestamps()
