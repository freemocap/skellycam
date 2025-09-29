import asyncio
import struct
import time
import tempfile
import mmap
from pathlib import Path
from collections import deque
import numpy as np

import flatbuffers
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import generated FlatBuffer code
import SharedData.CameraFrame as CameraFrame
import SharedData.SystemStatus as SystemStatus
import SharedData.SharedMessage as SharedMessage
import cv2

class FileBuffer:
    """Manages a memory-mapped file for FAST sharing"""

    def __init__(self, *, name: str, size: int = 10 * 1024 * 1024) -> None:
        self.size: int = size
        self.file_path: Path = Path(tempfile.gettempdir()) / f"fbuffer_{name}.bin"

        # Create file if it doesn't exist
        if not self.file_path.exists():
            with open(self.file_path, 'wb') as f:
                f.write(b'\x00' * size)

        # Open file and create memory map
        self.file_handle = open(self.file_path, 'r+b')
        self.mmap = mmap.mmap(self.file_handle.fileno(), size)

    def write_flatbuffer(self, *, builder: flatbuffers.Builder) -> None:
        """Write FlatBuffer data to memory-mapped file (NO disk I/O!)"""
        buf = builder.Output()

        # Write size prefix (4 bytes) then data
        size_bytes = struct.pack('<I', len(buf))

        # Write directly to memory map - FAST!
        self.mmap.seek(0)
        self.mmap.write(size_bytes)
        self.mmap.write(bytes(buf))
        # NO flush() call - memory map is already shared!

    def close(self) -> None:
        """Clean up resources"""
        if self.mmap:
            self.mmap.close()
        if self.file_handle:
            self.file_handle.close()


class CameraSimulator:
    """Simulates camera data generation - OPTIMIZED"""

    def __init__(self) -> None:
        self.frame_counter: int = 0
        self.buffer: FileBuffer = FileBuffer(name="camera_data")
        self.frame_times: deque[float] = deque(maxlen=30)
        self.last_frame_time: float = 0.0

        # 1080p settings
        self.width: int = 1280
        self.height: int = 720
        self.channels: int = 3  # RGB

        # OPTIMIZATION: Pre-allocate pixel buffer and reuse it
        self.pixels: np.ndarray = np.random.randint(
            0, 255,
            (self.width,  self.height,  self.channels),
            dtype=np.uint8
        )
        _, self.jpeg_data = cv2.imencode(
            ext='.jpg',
            img=self.pixels,
            params=[int(cv2.IMWRITE_JPEG_QUALITY), 80]
        )

        # OPTIMIZATION: Pre-allocate FlatBuffer builder and reuse it
        self.builder: flatbuffers.Builder = flatbuffers.Builder(8 * 1024 * 1024)

    def generate_frame(self, *, camera_id: int) -> None:
        """Generate a 1080p frame FAST - reusing buffers"""
        current_time = time.time()

        # Track frame timing
        if self.last_frame_time > 0:
            self.frame_times.append(current_time - self.last_frame_time)
        self.last_frame_time = current_time

        # OPTIMIZATION: Reset builder instead of creating new one
        self.builder.Clear()



        # Build pixels vector - reusing same buffer
        pixels_vector = self.builder.CreateNumpyVector(self.jpeg_data)#self.pixels)

        # Build CameraFrame
        CameraFrame.CameraFrameStart(self.builder)
        CameraFrame.CameraFrameAddCameraId(self.builder, camera_id)
        CameraFrame.CameraFrameAddTimestamp(self.builder, int(time.time() * 1000))
        CameraFrame.CameraFrameAddFrameNumber(self.builder, self.frame_counter)
        CameraFrame.CameraFrameAddWidth(self.builder, self.width)
        CameraFrame.CameraFrameAddHeight(self.builder, self.height)
        CameraFrame.CameraFrameAddPixels(self.builder, pixels_vector)
        frame = CameraFrame.CameraFrameEnd(self.builder)

        # Build SystemStatus
        fps = self.get_fps()
        message_str = self.builder.CreateString(f"Frame {self.frame_counter} @ {fps:.1f} FPS")

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

        # Write to memory-mapped file - FAST!
        self.buffer.write_flatbuffer(builder=self.builder)
        self.frame_counter += 1

    def get_fps(self) -> float:
        """Calculate current FPS based on recent frame times"""
        if len(self.frame_times) < 2:
            return 0.0

        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        if avg_frame_time > 0:
            return 1.0 / avg_frame_time
        return 0.0

    def print_stats(self) -> None:
        """Print current performance stats"""
        fps = self.get_fps()
        # frame_size_mb = self.jpeg_data.shape[0] / (1024 * 1024)
        frame_size_mb = self.pixels / (1024 * 1024)
        bandwidth_mb_s = fps * frame_size_mb

        print(f"🎬 Frame {self.frame_counter:5d} | "
              f"FPS: {fps:6.2f} | "
              f"Bandwidth: {bandwidth_mb_s:6.2f} MB/s | "
              f"Frame Size: {frame_size_mb:.2f} MB")


app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
simulator = CameraSimulator()


@app.get("/info")
async def get_info() -> dict[str, str | int]:
    """Return file path and info"""
    return {
        "file_path": str(simulator.buffer.file_path.absolute()),
        "size": simulator.buffer.size
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    print("✅ Client connected")

    try:
        # Send first frame immediately
        simulator.generate_frame(camera_id=1)
        simulator.print_stats()

        await websocket.send_json({
            "type": "frame_ready",
            "sequence": simulator.frame_counter,
        })

        await_acknowledgments = False # wait for client acknowledgments before sending new frames
        if await_acknowledgments:
            # Wait for acknowledgments and send new frames
            async for message in websocket.iter_text():
                import json
                data = json.loads(message)

                if data.get("type") == "ack":
                    # Client acknowledged last frame, send next one
                    simulator.generate_frame(camera_id=1)

                    # Only print stats every 30 frames to avoid terminal spam
                    if simulator.frame_counter % 30 == 0:
                        simulator.print_stats()

                    await websocket.send_json({
                        "type": "frame_ready",
                        "sequence": simulator.frame_counter,
                    })
        else: #send as fast as possible
            while True:
                await asyncio.sleep(0.001)  # Small sleep to avoid tight loop
                simulator.generate_frame(camera_id=1)

                # Only print stats every 100 frames to avoid terminal spam
                if simulator.frame_counter % 100 == 0:
                    simulator.print_stats()



    except WebSocketDisconnect:
        print("❌ Client disconnected")


if __name__ == "__main__":
    print("🚀 Starting FlatBuffer IPC Demo Server - OPTIMIZED!")
    print(f"📁 Shared file: {simulator.buffer.file_path.absolute()}")
    print(
        f"📐 Frame size: {simulator.width}x{simulator.height} RGB = {(simulator.width * simulator.height * 3) / (1024 * 1024):.2f} MB")
    print("🔥 Optimizations enabled:")
    print("   ✅ Memory-mapped file (no disk I/O)")
    print("   ✅ Reused FlatBuffer builder")
    print("   ✅ Reused pixel buffer")
    print("   ✅ No flush() calls")
    print("=" * 80)

    try:
        uvicorn.run(app=app, host="127.0.0.1", port=8009)
    finally:
        simulator.buffer.close()