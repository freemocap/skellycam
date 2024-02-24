import itertools
import json
import struct
from typing import Dict, Optional, List

import msgpack
from pydantic import BaseModel

from skellycam.backend.models.cameras.camera_id import CameraId
from skellycam.backend.models.cameras.frames.frame_payload import FramePayload


class MultiFramePayload(BaseModel):
    frames: Dict[CameraId, Optional[FramePayload]]

    @classmethod
    def create(cls, camera_ids: List[CameraId], **kwargs):
        return cls(frames={camera_id: None for camera_id in camera_ids}, **kwargs)

    @property
    def camera_ids(self) -> List[CameraId]:
        return [CameraId(camera_id) for camera_id in self.frames.keys()]

    @property
    def full(self):
        return not any([frame is None for frame in self.frames.values()])

    @property
    def empty(self):
        return all([frame is None for frame in self.frames.values()])

    @property
    def oldest_timestamp_ns(self) -> Optional[int]:
        return min(
            [frame.timestamp_ns for frame in self.frames.values() if frame is not None]
        )

    def resize(self, scale_factor: float):
        for frame in self.frames.values():
            if frame is not None:
                frame.resize(scale_factor=scale_factor)

    def add_frame(self, frame: FramePayload):
        self.frames[frame.camera_id] = frame

    def to_bytes(self) -> bytes:
        frames_data = [
            (index, frame.to_bytes())
            for index, frame in enumerate(self.frames.values())
            if frame is not None
        ]
        number_of_frames = len(frames_data)

        # We'll save the indices of the non-None frames, as well as their lengths
        header_info = [(index, len(frame_bytes)) for index, frame_bytes in frames_data]
        frames_bytes = b"".join([frame_bytes for _, frame_bytes in frames_data])

        # Header will be number of frames, followed by (index, length) pairs for each frame
        header = struct.pack(
            "i" + "ii" * number_of_frames,
            number_of_frames,
            *itertools.chain(*header_info),
        )

        return header + frames_bytes

    @classmethod
    def from_bytes(cls, byte_obj: bytes):
        number_of_frames = struct.unpack("i", byte_obj[:4])[0]
        byte_obj = byte_obj[4:]

        header_info = struct.unpack(
            "ii" * number_of_frames, byte_obj[: 8 * number_of_frames]
        )
        byte_obj = byte_obj[8 * number_of_frames :]

        # Unpack indices and lengths from header info
        indices, lengths = header_info[::2], header_info[1::2]

        frames = []
        byte_offset = 0
        for index, length in zip(indices, lengths):
            frame_bytes = byte_obj[byte_offset : byte_offset + length]
            frame = FramePayload.from_bytes(frame_bytes) if frame_bytes != b"" else None
            frames.append(frame)
            byte_offset += length

        return cls(frames={frame.camera_id: frame for frame in frames})

    def to_msgpack(self) -> bytes:
        # Convert the payload to a simpler dict representation
        frames_data = {
            camera_id: frame.to_msgpack() if frame else None
            for camera_id, frame in self.frames.items()
        }
        return msgpack.packb(frames_data, use_bin_type=True)

    @classmethod
    def from_msgpack(cls, msgpack_bytes: bytes):
        frames_dict = msgpack.unpackb(msgpack_bytes, raw=False)
        # Convert back to FramePayload objects
        frames = {
            CameraId(camera_id): FramePayload.from_msgpack(frame_bytes)
            if frame_bytes
            else None
            for camera_id, frame_bytes in frames_dict.items()
        }
        return cls(frames=frames)

    def to_json(self) -> str:
        frames_data = {
            str(camera_id): frame.dict() if frame else None
            for camera_id, frame in self.frames.items()
        }
        return json.dumps(frames_data)
