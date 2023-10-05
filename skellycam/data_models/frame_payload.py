from dataclasses import dataclass
import re
import numpy as np
import base64


@dataclass
class FramePayload:
    success: bool = False
    image: np.ndarray = None
    timestamp_ns: float = None
    number_of_frames_received: int = None
    camera_id: int = None  # changed camera_id to int

    def to_bytes(self):
        camera_id_bytes = self.camera_id.to_bytes(4, byteorder='little')  # handle camera_id as int

        dtype_str, shape_str = str(self.image.dtype), str(self.image.shape)
        timestamp_ns = np.array([self.timestamp_ns], dtype=float)  # create a numpy array
        fields_as_bytes = [
            self.success.to_bytes(1, byteorder='little'),
            dtype_str.encode(),
            b' ',
            shape_str.encode(),
            b' ',
            self.image.tobytes(),
            timestamp_ns.tobytes(),  # now you can call tobytes properly
            self.number_of_frames_received.to_bytes(8, byteorder='little'),
            camera_id_bytes,
        ]
        return b''.join(fields_as_bytes)

    @classmethod
    def from_bytes(cls, b):
        success, b = bool(int.from_bytes(b[0:1], byteorder='little')), b[1:]
        dtype_str, b = b.split(b' ', 1)
        shape_str, b = b.split(b' ', 1)
        dtype = np.dtype(dtype_str.decode())
        shape = tuple(map(int, re.findall(r'\b\d+\b', shape_str.decode())))
        image_size = np.prod(shape) * dtype.itemsize
        image = np.frombuffer(b[:image_size], dtype=dtype)
        image = image.reshape(shape)
        b = b[image_size:]

        timestamp_ns = np.frombuffer(b[:8], dtype=float)[0]
        b = b[8:]

        number_of_frames_received = int.from_bytes(b[:8], byteorder='little')
        b = b[8:]

        camera_id = int.from_bytes(b[:4], byteorder='little')  # handle camera_id as int
        b = b[4:]  # adjust the remaining bytes

        return cls(success=success,
                   image=image,
                   timestamp_ns=float(timestamp_ns),
                   number_of_frames_received=number_of_frames_received,
                   camera_id=camera_id)

def test_frame_payload():
    original_payload = FramePayload(
        success=True,
        image=np.random.rand(10, 10, 3),
        timestamp_ns=np.float64(np.random.rand()),  # ensure it's a np.float64
        number_of_frames_received=10,
        camera_id=0
    )

    bytes_payload = original_payload.to_bytes()
    restored_payload = FramePayload.from_bytes(bytes_payload)

    print("Original Image Shape: ", original_payload.image.shape)
    print("Restored Image Shape: ", restored_payload.image.shape)
    print("Are both images identical?: ", np.array_equal(original_payload.image, restored_payload.image))

    assert original_payload.success == restored_payload.success, f"Expected success={original_payload.success}, but got {restored_payload.success}"
    assert np.array_equal(original_payload.image, restored_payload.image), "Image arrays don't match."
    assert original_payload.timestamp_ns == restored_payload.timestamp_ns, f"Expected timestamp_ns={original_payload.timestamp_ns}, but got {restored_payload.timestamp_ns}"
    assert original_payload.number_of_frames_received == restored_payload.number_of_frames_received, f"Expected no of frames={original_payload.number_of_frames_received}, but got {restored_payload.number_of_frames_received}"
    assert original_payload.camera_id == restored_payload.camera_id, f"Expected camera_id={original_payload.camera_id}, but got {restored_payload.camera_id}"

if __name__ == '__main__':
    test_frame_payload()