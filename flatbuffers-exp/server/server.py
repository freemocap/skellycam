import asyncio
import os
import struct
import time
import tempfile
import mmap
from pathlib import Path
from collections import deque
from typing import Deque
from dataclasses import dataclass
import numpy as np

import flatbuffers
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import generated FlatBuffer code
import generated.SharedData.CameraFrame as CameraFrame
import generated.SharedData.SystemStatus as SystemStatus
import generated.SharedData.SharedMessage as SharedMessage

file_path = Path(tempfile.gettempdir()) / "ringbuffer_camera_data.bin"
if file_path.exists():
    os.remove(file_path)
    print(f"Deleted existing file: {file_path}")


@dataclass
class RingBufferHeader:
    """Ring buffer header (64 bytes)"""
    magic: int = 0xDEADBEEF
    version: int = 3
    capacity: int = 100
    max_frame_size: int = 10 * 1024 * 1024
    write_index: int = 0
    latest_frame_number: int = 0
    total_writes: int = 0
    metadata_table_offset: int = 0

    HEADER_SIZE = 64

    def to_bytes(self) -> bytes:
        """Pack header to 64 bytes"""
        data = struct.pack(
            '<IIIIQQQQ',
            self.magic,
            self.version,
            self.capacity,
            self.max_frame_size,
            self.write_index,
            self.latest_frame_number,
            self.total_writes,
            self.metadata_table_offset
        )
        # Pad to 64 bytes
        return data + b'\x00' * (self.HEADER_SIZE - len(data))

    @classmethod
    def from_bytes(cls, data: bytes) -> 'RingBufferHeader':
        """Unpack header from bytes"""
        unpacked = struct.unpack('<IIIIQQQQ', data[:48])
        return cls(
            magic=unpacked[0],
            version=unpacked[1],
            capacity=unpacked[2],
            max_frame_size=unpacked[3],
            write_index=unpacked[4],
            latest_frame_number=unpacked[5],
            total_writes=unpacked[6],
            metadata_table_offset=unpacked[7]
        )


@dataclass
class FrameMetadata:
    """Metadata entry for quick frame lookup (32 bytes)"""
    frame_number: int = 0
    sequence: int = 0
    slot_index: int = 0
    frame_size: int = 0
    timestamp: int = 0
    valid: int = 1

    METADATA_SIZE = 32

    def to_bytes(self) -> bytes:
        """Pack metadata to 32 bytes"""
        return struct.pack(
            '<IIIQQQ',
            self.frame_number,
            self.sequence,
            self.slot_index,
            self.frame_size,
            self.timestamp,
            self.valid
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> 'FrameMetadata':
        """Unpack metadata from bytes"""
        unpacked = struct.unpack('<IIIQQQ', data[:cls.METADATA_SIZE])
        return cls(
            frame_number=unpacked[0],
            sequence=unpacked[1],
            slot_index=unpacked[2],
            frame_size=unpacked[3],
            timestamp=unpacked[4],
            valid=unpacked[5]
        )


@dataclass
class FrameSlotHeader:
    """Header for each frame slot (24 bytes)"""
    valid: int = 0
    frame_number: int = 0
    frame_size: int = 0
    timestamp: int = 0

    SLOT_HEADER_SIZE = 24

    def to_bytes(self) -> bytes:
        """Pack slot header to 24 bytes"""
        return struct.pack('<IIQQ', self.valid, self.frame_number, self.frame_size, self.timestamp)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'FrameSlotHeader':
        """Unpack slot header from bytes"""
        unpacked = struct.unpack('<IIQQ', data[:cls.SLOT_HEADER_SIZE])
        return cls(
            valid=unpacked[0],
            frame_number=unpacked[1],
            frame_size=unpacked[2],
            timestamp=unpacked[3]
        )


class RingBufferWriter:
    """Simplified ring buffer writer"""

    def __init__(
            self,
            *,
            name: str,
            capacity: int = 100,
            max_frame_size: int = 10 * 1024 * 1024
    ) -> None:
        self.capacity: int = capacity
        self.max_frame_size: int = max_frame_size
        self.frame_counter: int = 0

        # Calculate layout
        self.slot_size: int = FrameSlotHeader.SLOT_HEADER_SIZE + max_frame_size
        self.metadata_table_offset: int = RingBufferHeader.HEADER_SIZE
        self.metadata_table_size: int = FrameMetadata.METADATA_SIZE * capacity
        self.slots_offset: int = self.metadata_table_offset + self.metadata_table_size
        self.total_size: int = self.slots_offset + (self.slot_size * capacity)

        self.file_path: Path = Path(tempfile.gettempdir()) / f"ringbuffer_{name}.bin"

        # Create and initialize file
        if not self.file_path.exists():
            self._initialize_file()

        # Memory map the file
        self.file_handle = open(self.file_path, 'r+b')
        self.mmap = mmap.mmap(self.file_handle.fileno(), self.total_size)

        # Load header
        self.header: RingBufferHeader = RingBufferHeader.from_bytes(
            self.mmap[:RingBufferHeader.HEADER_SIZE]
        )

        # Resume from last frame number
        self.frame_counter = self.header.latest_frame_number

        print(f"Ring Buffer Created:")
        print(f"   Path: {self.file_path}")
        print(f"   Capacity: {capacity} frames")
        print(f"   Total size: {self.total_size / (1024 * 1024):.2f} MB")
        print(f"   Last frame number: {self.frame_counter}")

    def _initialize_file(self) -> None:
        """Initialize ring buffer file structure"""
        with open(self.file_path, 'wb') as f:
            # Write header
            header = RingBufferHeader(
                capacity=self.capacity,
                max_frame_size=self.max_frame_size,
                metadata_table_offset=self.metadata_table_offset
            )
            f.write(header.to_bytes())

            # Write empty metadata table
            empty_metadata = FrameMetadata(valid=0)
            for _ in range(self.capacity):
                f.write(empty_metadata.to_bytes())

            # Write empty slots
            empty_slot = FrameSlotHeader(valid=0)
            for _ in range(self.capacity):
                f.write(empty_slot.to_bytes())
                f.write(b'\x00' * self.max_frame_size)

    def get_slot_offset(self, *, index: int) -> int:
        """Get byte offset for a slot"""
        slot_num = index % self.capacity
        return self.slots_offset + (slot_num * self.slot_size)

    def get_metadata_offset(self, *, index: int) -> int:
        """Get byte offset for metadata entry"""
        slot_num = index % self.capacity
        return self.metadata_table_offset + (slot_num * FrameMetadata.METADATA_SIZE)

    def write_frame(self, *, flatbuffer_data: bytes) -> bool:
        """Write frame to ring buffer"""
        if len(flatbuffer_data) > self.max_frame_size:
            print(f"Frame too large: {len(flatbuffer_data)} > {self.max_frame_size}")
            return False

        self.frame_counter += 1
        frame_number = self.frame_counter
        timestamp = int(time.time() * 1_000_000)

        # Get slot index
        write_idx = self.header.write_index
        slot_index = write_idx % self.capacity
        slot_offset = self.get_slot_offset(index=write_idx)

        # Write frame data
        slot_header = FrameSlotHeader(
            valid=1,
            frame_number=frame_number,
            frame_size=len(flatbuffer_data),
            timestamp=timestamp
        )

        self.mmap.seek(slot_offset)
        self.mmap.write(slot_header.to_bytes())
        self.mmap.write(flatbuffer_data)

        # Write metadata entry
        metadata = FrameMetadata(
            frame_number=frame_number,
            sequence=write_idx,
            slot_index=slot_index,
            frame_size=len(flatbuffer_data),
            timestamp=timestamp,
            valid=1
        )

        metadata_offset = self.get_metadata_offset(index=write_idx)
        self.mmap.seek(metadata_offset)
        self.mmap.write(metadata.to_bytes())

        # Update header
        self.header.write_index += 1
        self.header.latest_frame_number = frame_number
        self.header.total_writes += 1

        self.mmap.seek(0)
        self.mmap.write(self.header.to_bytes())
        self.mmap.flush()

        return True

    def get_latest_frame_number(self) -> int:
        """Get the latest written frame number"""
        self.mmap.seek(0)
        current_header = RingBufferHeader.from_bytes(
            self.mmap[:RingBufferHeader.HEADER_SIZE]
        )
        return current_header.latest_frame_number

    def get_stats(self) -> dict[str, int | float]:
        """Get buffer statistics"""
        self.mmap.seek(0)
        current_header = RingBufferHeader.from_bytes(
            self.mmap[:RingBufferHeader.HEADER_SIZE]
        )

        return {
            'write_index': current_header.write_index,
            'latest_frame_number': current_header.latest_frame_number,
            'capacity': self.capacity,
            'total_writes': current_header.total_writes,
            'utilization_pct': ((current_header.write_index % self.capacity) / self.capacity * 100),
        }

    def close(self) -> None:
        """Clean up resources"""
        if self.mmap:
            self.mmap.close()
        if self.file_handle:
            self.file_handle.close()


class CameraSimulator:
    """Generates raw RGB frames"""

    def __init__(self) -> None:
        self.buffer: RingBufferWriter = RingBufferWriter(
            name="camera_data",
            capacity=100,
            max_frame_size=10 * 1024 * 1024
        )

        self.write_times: Deque[float] = deque(maxlen=100)
        self.last_write_time: float = 0.0
        self.total_bytes_written: int = 0

        # 720p RGB settings
        self.width: int = 1280
        self.height: int = 720
        self.channels: int = 3

        # Pre-allocate RGB buffer
        self.pixels: np.ndarray = self._create_test_pattern()
        self.builder: flatbuffers.Builder = flatbuffers.Builder(10 * 1024 * 1024)

    def _create_test_pattern(self) -> np.ndarray:
        """Create a colorful test pattern"""
        y, x = np.mgrid[0:self.height, 0:self.width]

        r = ((x / self.width) * 255).astype(np.uint8)
        g = ((y / self.height) * 255).astype(np.uint8)
        b = np.full((self.height, self.width), 128, dtype=np.uint8)

        return np.stack([r, g, b], axis=2)

    def update_test_pattern(self) -> None:
        """Slightly modify pattern each frame"""
        frame_num = self.buffer.frame_counter
        offset = (frame_num % 255)
        self.pixels[:, :, 0] = (self.pixels[:, :, 0] + offset) % 255

    def generate_frame(self, *, camera_id: int) -> int:
        """Generate frame and return frame number"""
        current_time = time.perf_counter()

        if self.last_write_time > 0:
            self.write_times.append(current_time - self.last_write_time)
        self.last_write_time = current_time

        if self.buffer.frame_counter % 10 == 0:
            self.update_test_pattern()

        # Build FlatBuffer
        self.builder.Clear()

        pixels_vector = self.builder.CreateNumpyVector(self.pixels.flatten())

        CameraFrame.CameraFrameStart(self.builder)
        CameraFrame.CameraFrameAddCameraId(self.builder, camera_id)
        CameraFrame.CameraFrameAddTimestamp(self.builder, int(time.time() * 1000))
        CameraFrame.CameraFrameAddFrameNumber(self.builder, self.buffer.frame_counter + 1)
        CameraFrame.CameraFrameAddWidth(self.builder, self.width)
        CameraFrame.CameraFrameAddHeight(self.builder, self.height)
        CameraFrame.CameraFrameAddChannels(self.builder, self.channels)
        CameraFrame.CameraFrameAddPixels(self.builder, pixels_vector)
        frame = CameraFrame.CameraFrameEnd(self.builder)

        fps = self.get_write_fps()
        message_str = self.builder.CreateString(
            f"Frame {self.buffer.frame_counter + 1} @ {fps:.1f} FPS"
        )

        SystemStatus.SystemStatusStart(self.builder)
        SystemStatus.SystemStatusAddFps(self.builder, fps)
        SystemStatus.SystemStatusAddCpuUsage(self.builder, 45.5)
        SystemStatus.SystemStatusAddActiveCameras(self.builder, 1)
        SystemStatus.SystemStatusAddMessage(self.builder, message_str)
        status = SystemStatus.SystemStatusEnd(self.builder)

        SharedMessage.SharedMessageStart(self.builder)
        SharedMessage.SharedMessageAddMagic(self.builder, 0xDEADBEEF)
        SharedMessage.SharedMessageAddSequence(self.builder, self.buffer.frame_counter + 1)
        SharedMessage.SharedMessageAddFrame(self.builder, frame)
        SharedMessage.SharedMessageAddStatus(self.builder, status)
        message = SharedMessage.SharedMessageEnd(self.builder)

        self.builder.Finish(message)

        # Write to ring buffer
        fb_data = bytes(self.builder.Output())
        success = self.buffer.write_frame(flatbuffer_data=fb_data)

        if success:
            self.total_bytes_written += len(fb_data)
            return self.buffer.frame_counter
        else:
            print("Failed to write frame")
            return 0

    def get_write_fps(self) -> float:
        if len(self.write_times) < 2:
            return 0.0

        avg_frame_time = sum(self.write_times) / len(self.write_times)
        if avg_frame_time > 0:
            return 1.0 / avg_frame_time
        return 0.0

    def print_stats(self) -> None:
        fps = self.get_write_fps()
        frame_size_mb = (self.width * self.height * self.channels) / (1024 * 1024)
        bandwidth_mb_s = fps * frame_size_mb
        total_mb = self.total_bytes_written / (1024 * 1024)

        print(
            f"PYTHON | Frame {self.buffer.frame_counter:6d} | "
            f"Write: {fps:6.1f} FPS | "
            f"BW: {bandwidth_mb_s:6.1f} MB/s | "
            f"Total: {total_mb:7.1f} MB"
        )


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

simulator = CameraSimulator()
running = False


@app.get("/info")
async def get_info() -> dict[str, str | int]:
    return {
        "file_path": str(simulator.buffer.file_path.absolute()),
        "capacity": simulator.buffer.capacity,
        "slot_size": simulator.buffer.slot_size,
        "total_size": simulator.buffer.total_size,
        "width": simulator.width,
        "height": simulator.height,
        "channels": simulator.channels,
        "latest_frame_number": simulator.buffer.get_latest_frame_number(),
    }


@app.get("/stats")
async def get_stats() -> dict[str, int | float]:
    """Get ring buffer statistics"""
    return simulator.buffer.get_stats()


@app.get("/latest_frame_number")
async def get_latest_frame_number() -> dict[str, int]:
    """Get the latest frame number available"""
    return {"latest_frame_number": simulator.buffer.get_latest_frame_number()}


@app.post("/start")
async def start_streaming() -> dict[str, str]:
    global running
    if not running:
        running = True
        asyncio.create_task(generation_loop())
        return {"status": "started"}
    return {"status": "already_running"}


@app.post("/stop")
async def stop_streaming() -> dict[str, str]:
    global running
    running = False
    return {"status": "stopped"}


async def generation_loop() -> None:
    """Generate frames at maximum speed"""
    global running
    print("\n" + "=" * 80)
    print("Simplified Ring Buffer IPC")
    print("=" * 80 + "\n")

    while running:
        simulator.generate_frame(camera_id=1)

        if simulator.buffer.frame_counter % 1000 == 0:
            simulator.print_stats()

        if simulator.buffer.frame_counter % 100 == 0:
            await asyncio.sleep(0)


if __name__ == "__main__":
    print("Simplified FlatBuffer Ring Buffer IPC")
    print(f"Shared file: {simulator.buffer.file_path.absolute()}")
    print(f"Frame: {simulator.width}x{simulator.height}x{simulator.channels} = "
          f"{(simulator.width * simulator.height * simulator.channels) / (1024 * 1024):.2f} MB")
    print(f"Ring buffer: {simulator.buffer.capacity} slots = "
          f"{simulator.buffer.total_size / (1024 * 1024):.2f} MB total")
    print("\nCall POST http://localhost:8009/start to begin\n")

    try:
        uvicorn.run(app=app, host="127.0.0.1", port=8009, log_level="warning")
    finally:
        simulator.buffer.close()