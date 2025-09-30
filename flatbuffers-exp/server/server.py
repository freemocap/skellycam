import asyncio
import struct
import time
import tempfile
import mmap
from pathlib import Path
from collections import deque
import numpy as np
from typing import Deque

import flatbuffers
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import generated FlatBuffer code
import generated.SharedData.CameraFrame as CameraFrame
import generated.SharedData.SystemStatus as SystemStatus
import generated.SharedData.SharedMessage as SharedMessage


class FileBuffer:
    """Memory-mapped file for zero-copy IPC"""

    def __init__(self, *, name: str, size: int = 20 * 1024 * 1024) -> None:
        self.size: int = size
        self.file_path: Path = Path(tempfile.gettempdir()) / f"fbuffer_{name}.bin"

        if not self.file_path.exists():
            with open(self.file_path, 'wb') as f:
                f.write(b'\x00' * size)

        self.file_handle = open(self.file_path, 'r+b')
        self.mmap = mmap.mmap(self.file_handle.fileno(), size)

    def write_flatbuffer(self, *, builder: flatbuffers.Builder) -> None:
        """Write FlatBuffer to mmap - instant visibility to Rust"""
        buf = builder.Output()
        size_bytes = struct.pack('<I', len(buf))

        self.mmap.seek(0)
        self.mmap.write(size_bytes)
        self.mmap.write(bytes(buf))
        # No flush needed - mmap is shared memory!

    def close(self) -> None:
        if self.mmap:
            self.mmap.close()
        if self.file_handle:
            self.file_handle.close()


class CameraSimulator:
    """Generates raw RGB frames for maximum throughput"""

    def __init__(self) -> None:
        self.frame_counter: int = 0
        self.buffer: FileBuffer = FileBuffer(name="camera_data", size=20 * 1024 * 1024)

        self.write_times: Deque[float] = deque(maxlen=100)
        self.last_write_time: float = 0.0
        self.total_bytes_written: int = 0

        # 720p RGB settings
        self.width: int = 1280
        self.height: int = 720
        self.channels: int = 3

        # Pre-allocate RGB buffer - reuse it!
        # Create a gradient pattern for visual verification
        self.pixels: np.ndarray = self._create_test_pattern()

        # Pre-allocate FlatBuffer builder
        self.builder: flatbuffers.Builder = flatbuffers.Builder(10 * 1024 * 1024)

    def _create_test_pattern(self) -> np.ndarray:
        """Create a colorful test pattern that changes each frame"""
        y, x = np.mgrid[0:self.height, 0:self.width]

        # Create RGB channels with patterns
        r = ((x / self.width) * 255).astype(np.uint8)
        g = ((y / self.height) * 255).astype(np.uint8)
        b = np.full((self.height, self.width), 128, dtype=np.uint8)

        return np.stack([r, g, b], axis=2)

    def update_test_pattern(self) -> None:
        """Slightly modify pattern each frame for visual verification"""
        # Rotate hue slightly
        offset = (self.frame_counter % 255)
        self.pixels[:, :, 0] = (self.pixels[:, :, 0] + offset) % 255

    def generate_frame(self, *, camera_id: int) -> None:
        """Generate frame with RAW RGB data - NO JPEG ENCODING"""
        current_time = time.perf_counter()

        if self.last_write_time > 0:
            self.write_times.append(current_time - self.last_write_time)
        self.last_write_time = current_time

        # Update pattern for visual verification
        if self.frame_counter % 10 == 0:
            self.update_test_pattern()

        # Reset builder
        self.builder.Clear()

        # RAW RGB data - just the bytes, no encoding!
        pixels_vector = self.builder.CreateNumpyVector(self.pixels.flatten())

        # Build CameraFrame with raw data
        CameraFrame.CameraFrameStart(self.builder)
        CameraFrame.CameraFrameAddCameraId(self.builder, camera_id)
        CameraFrame.CameraFrameAddTimestamp(self.builder, int(time.time() * 1000))
        CameraFrame.CameraFrameAddFrameNumber(self.builder, self.frame_counter)
        CameraFrame.CameraFrameAddWidth(self.builder, self.width)
        CameraFrame.CameraFrameAddHeight(self.builder, self.height)
        CameraFrame.CameraFrameAddChannels(self.builder, self.channels)
        CameraFrame.CameraFrameAddPixels(self.builder, pixels_vector)
        frame = CameraFrame.CameraFrameEnd(self.builder)

        # Build SystemStatus
        fps = self.get_write_fps()
        message_str = self.builder.CreateString(
            f"Frame {self.frame_counter} @ {fps:.1f} FPS"
        )

        SystemStatus.SystemStatusStart(self.builder)
        SystemStatus.SystemStatusAddFps(self.builder, fps)
        SystemStatus.SystemStatusAddCpuUsage(self.builder, 45.5)
        SystemStatus.SystemStatusAddActiveCameras(self.builder, 1)
        SystemStatus.SystemStatusAddMessage(self.builder, message_str)
        status = SystemStatus.SystemStatusEnd(self.builder)

        # Build SharedMessage
        SharedMessage.SharedMessageStart(self.builder)
        SharedMessage.SharedMessageAddMagic(self.builder, 0xDEADBEEF)
        SharedMessage.SharedMessageAddSequence(self.builder, self.frame_counter)
        SharedMessage.SharedMessageAddFrame(self.builder, frame)
        SharedMessage.SharedMessageAddStatus(self.builder, status)
        message = SharedMessage.SharedMessageEnd(self.builder)

        self.builder.Finish(message)

        # Write to mmap - instant!
        self.buffer.write_flatbuffer(builder=self.builder)

        self.total_bytes_written += len(self.builder.Output())
        self.frame_counter += 1

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
            f"🎬 PYTHON | Frame {self.frame_counter:6d} | "
            f"Write: {fps:6.1f} FPS | "
            f"Bandwidth: {bandwidth_mb_s:6.1f} MB/s | "
            f"Total: {total_mb:7.1f} MB | "
            f"Raw size: {frame_size_mb:.2f} MB"
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
        "size": simulator.buffer.size,
        "width": simulator.width,
        "height": simulator.height,
        "channels": simulator.channels,
    }


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
    print("🚀 RAW RGB MODE: Maximum throughput, no encoding overhead")
    print("=" * 80 + "\n")

    while running:
        simulator.generate_frame(camera_id=1)

        if simulator.frame_counter % 1000 == 0:
            simulator.print_stats()

        # Yield occasionally to not block event loop
        if simulator.frame_counter % 100 == 0:
            await asyncio.sleep(0)


if __name__ == "__main__":
    print("🚀 FlatBuffer IPC - RAW RGB MODE")
    print(f"📂 Shared file: {simulator.buffer.file_path.absolute()}")
    print(f"📐 Frame: {simulator.width}x{simulator.height}x{simulator.channels} = "
          f"{(simulator.width * simulator.height * simulator.channels) / (1024 * 1024):.2f} MB")
    print("🔥 Optimizations:")
    print("   ✅ Raw RGB (no JPEG encoding)")
    print("   ✅ Memory-mapped file (zero-copy)")
    print("   ✅ Reused buffers")
    print("   ✅ Rust will decode FlatBuffer natively")
    print("\n⚡ Expected: 500-2000+ write FPS\n")
    print("Call POST http://localhost:8009/start to begin\n")

    try:
        uvicorn.run(app=app, host="127.0.0.1", port=8009, log_level="warning")
    finally:
        simulator.buffer.close()