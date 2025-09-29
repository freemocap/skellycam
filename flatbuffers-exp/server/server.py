import asyncio
import struct
import time
import tempfile
from pathlib import Path
import numpy as np

import flatbuffers
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import generated FlatBuffer code
import SharedData.CameraFrame as CameraFrame
import SharedData.SystemStatus as SystemStatus
import SharedData.SharedMessage as SharedMessage


class FileBuffer:
    """Manages a file for sharing data (cross-platform)"""

    def __init__(self, *, name: str, size: int = 1024 * 1024) -> None:
        self.size: int = size
        self.file_path: Path = Path(tempfile.gettempdir()) / f"fbuffer_{name}.bin"

        # Create file if it doesn't exist
        if not self.file_path.exists():
            self.file_path.write_bytes(b'\x00' * size)

    def write_flatbuffer(self, *, builder: flatbuffers.Builder) -> None:
        """Write FlatBuffer data to file"""
        buf = builder.Output()

        # Write size prefix (4 bytes) then data
        size_bytes = struct.pack('<I', len(buf))

        with open(self.file_path, 'r+b') as f:
            f.seek(0)
            f.write(size_bytes)
            f.write(bytes(buf))
            f.flush()


class CameraSimulator:
    """Simulates camera data generation"""

    def __init__(self) -> None:
        self.frame_counter: int = 0
        self.buffer: FileBuffer = FileBuffer(name="camera_data")

    def generate_frame(self, *, camera_id: int) -> None:
        """Generate a test frame and write to shared file"""
        builder = flatbuffers.Builder(1024 * 100)

        # Create fake pixel data (small for demo - 100x100 RGB)
        width: int = 100
        height: int = 100
        pixels: np.ndarray = np.random.randint(0, 255, width * height * 3, dtype=np.uint8)

        # Build pixels vector - use builder's CreateNumpyVector or CreateByteVector
        pixels_vector = builder.CreateNumpyVector(pixels)

        # Build CameraFrame using the correct generated API
        CameraFrame.CameraFrameStart(builder)
        CameraFrame.CameraFrameAddCameraId(builder, camera_id)
        CameraFrame.CameraFrameAddTimestamp(builder, int(time.time() * 1000))
        CameraFrame.CameraFrameAddFrameNumber(builder, self.frame_counter)
        CameraFrame.CameraFrameAddWidth(builder, width)
        CameraFrame.CameraFrameAddHeight(builder, height)
        CameraFrame.CameraFrameAddPixels(builder, pixels_vector)
        frame = CameraFrame.CameraFrameEnd(builder)

        # Build SystemStatus message string first (must be created before SystemStatus)
        message_str = builder.CreateString(f"Frame {self.frame_counter} from camera {camera_id}")

        SystemStatus.SystemStatusStart(builder)
        SystemStatus.SystemStatusAddFps(builder, 30.0)
        SystemStatus.SystemStatusAddCpuUsage(builder, 45.5 + (self.frame_counter % 20))
        SystemStatus.SystemStatusAddActiveCameras(builder, 1)
        SystemStatus.SystemStatusAddMessage(builder, message_str)
        status = SystemStatus.SystemStatusEnd(builder)

        # Build SharedMessage
        SharedMessage.SharedMessageStart(builder)
        SharedMessage.SharedMessageAddMagic(builder, 0xDEADBEEF)
        SharedMessage.SharedMessageAddSequence(builder, self.frame_counter)
        SharedMessage.SharedMessageAddFrame(builder, frame)
        SharedMessage.SharedMessageAddStatus(builder, status)
        message = SharedMessage.SharedMessageEnd(builder)

        builder.Finish(message)

        # Write to file
        self.buffer.write_flatbuffer(builder=builder)
        self.frame_counter += 1


app = FastAPI()

# Enable CORS for Electron app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
simulator = CameraSimulator()
connected_clients: set[WebSocket] = set()


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
    connected_clients.add(websocket)

    try:
        while True:
            # Generate new frame
            simulator.generate_frame(camera_id=1)

            # Notify client
            await websocket.send_json({
                "type": "frame_update",
                "sequence": simulator.frame_counter,
                "timestamp": time.time()
            })

            # Simulate 30 FPS
            await asyncio.sleep(1/30)
            

    except WebSocketDisconnect:
        connected_clients.remove(websocket)


if __name__ == "__main__":
    print("🚀 Starting FlatBuffer IPC Demo Server")
    print(f"📁 Shared file: {simulator.buffer.file_path.absolute()}")
    uvicorn.run(app=app, host="127.0.0.1", port=8009)
