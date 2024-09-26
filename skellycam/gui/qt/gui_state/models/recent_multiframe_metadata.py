from typing import List, Dict

from pydantic import BaseModel

from skellycam.core import CameraId
from skellycam.core.frames.payloads.multi_frame_payload import MultiFrameMetadata
from skellycam.gui.qt.gui_state.models.camera_framerate_stats import CameraFramerateStats


class RecentMultiframeMetadata(BaseModel):
    recent_metadata: List[MultiFrameMetadata] = []
    framerate_stats_by_camera: Dict[CameraId, CameraFramerateStats] = {}
    max_recent_metadata: int = 30
    camera_ids: List[CameraId]

    @classmethod
    def from_multi_frame_metadata(cls, multi_frame_metadata: MultiFrameMetadata) -> 'RecentMultiframeMetadata':
        return cls(recent_metadata=[multi_frame_metadata],
                   framerate_stats_by_camera={
                       camera_id: CameraFramerateStats.from_frame_metadata(frame_metadata=frame_metadata,
                                                                           utc_mapping=multi_frame_metadata.utc_ns_to_perf_ns
                                                                           )
                       for camera_id, frame_metadata in multi_frame_metadata.frame_metadata_by_camera.items()
                   },
                   camera_ids=list(multi_frame_metadata.frame_metadata_by_camera.keys())
                   )

    def add_multiframe_metadata(self, metadata: MultiFrameMetadata):
        if self.camera_ids != list(metadata.frame_metadata_by_camera.keys()):
            raise ValueError("Camera IDs do not match")
        self.recent_metadata.append(metadata)
        if len(self.recent_metadata) > self.max_recent_metadata:
            self.recent_metadata.pop(0)

        for camera_id, frame_metadata in metadata.frame_metadata_by_camera.items():
            if camera_id not in self.framerate_stats_by_camera:
                self.framerate_stats_by_camera[camera_id] = CameraFramerateStats.from_frame_metadata(
                    frame_metadata=frame_metadata,
                    utc_mapping=metadata.utc_ns_to_perf
                )
            self.framerate_stats_by_camera[camera_id].add_frame_metadata(frame_metadata)
