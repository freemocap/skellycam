"""
Simplified H264 server - sends every frame as a keyframe
Requires: pip install av opencv-python fastapi websockets uvicorn
"""

import av
import cv2
import asyncio
import base64
import json
import io
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleH264Encoder:
    """Simplified encoder - every frame is a keyframe"""

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = 0

        # Create output container
        self.output_buffer = io.BytesIO()
        self.container = av.open(self.output_buffer, mode='w', format='h264')

        # Configure stream for all I-frames
        self.stream = self.container.add_stream('libx264', rate=fps)
        self.stream.width = width
        self.stream.height = height
        self.stream.pix_fmt = 'yuv420p'
        self.stream.bit_rate = 4000000  # Higher bitrate for all-keyframe

        # Force every frame to be a keyframe
        self.stream.gop_size = 1  # CRITICAL: GOP of 1 = every frame is keyframe
        self.stream.codec_context.options = {
            'preset': 'ultrafast',
            'tune': 'zerolatency',
            'profile': 'baseline',
            'g': '1',           # Force GOP size 1
            'keyint_min': '1',  # Min keyframe interval 1
            'bf': '0',          # No B-frames
            'refs': '1'
        }

        logger.info(f"Encoder ready: {width}x{height} @ {fps}fps (all keyframes)")

    def encode_frame(self, bgr_frame) -> bytes | None:
        """Encode single frame as keyframe and return raw H264 data"""
        try:
            # Convert BGR to YUV420p
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            frame = av.VideoFrame.from_ndarray(rgb_frame, format='rgb24')
            frame = frame.reformat(format='yuv420p')

            # Set timestamp
            frame.pts = self.frame_count
            frame.pict_type = av.video.frame.PictureType.I  # Force I-frame
            self.frame_count += 1

            # Encode and get raw bytes
            packets = self.stream.encode(frame)
            for packet in packets:
                return bytes(packet)  # Return first packet bytes

        except Exception as e:
            logger.error(f"Encode error: {e}")

        return None

class CameraCapture:
    """Simple camera capture"""

    def __init__(self, camera_index: int = 0):
        self.cap = cv2.VideoCapture(camera_index)

        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_index}")

        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Get actual properties
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30

        logger.info(f"Camera ready: {self.width}x{self.height} @ {self.fps}fps")

    def read_frame(self):
        ret, frame = self.cap.read()
        return frame if ret else None

    def release(self):
        if self.cap:
            self.cap.release()

app = FastAPI()

@app.websocket("/stream")
async def stream_video(websocket: WebSocket):
    """Simplified WebSocket streaming - all keyframes"""
    await websocket.accept()

    camera = None
    encoder = None

    try:
        # Initialize camera
        camera = CameraCapture(camera_index=0)

        # Initialize encoder
        encoder = SimpleH264Encoder(
            width=camera.width,
            height=camera.height,
            fps=camera.fps
        )

        logger.info("Client connected, starting all-keyframe stream")

        # Send initial config
        config = {
            'width': camera.width,
            'height': camera.height,
            'fps': camera.fps
        }
        await websocket.send_json({
            'type': 'config',
            'config': config
        })

        # Stream frames
        frame_count = 0
        while True:
            # Read frame from camera
            frame = camera.read_frame()
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            # Encode as keyframe
            h264_data = encoder.encode_frame(frame)
            if h264_data:
                # Send as base64
                await websocket.send_json({
                    'type': 'frame',
                    'data': base64.b64encode(h264_data).decode('utf-8'),
                    'timestamp': frame_count / camera.fps,
                    'is_keyframe': True  # Always true now
                })

                frame_count += 1
                if frame_count % 30 == 0:
                    logger.info(f"Streamed {frame_count} keyframes")



    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Stream error: {e}")
    finally:
        if camera:
            camera.release()
        if encoder and hasattr(encoder, 'container'):
            try:
                encoder.container.close()
            except:
                pass

@app.get("/")
async def root():
    return {"status": "Simplified H264 Server (All Keyframes)"}

if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("Simplified H264 Server - All Keyframes")
    print("=" * 50)
    print("WebSocket: ws://localhost:8000/stream")
    print("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")