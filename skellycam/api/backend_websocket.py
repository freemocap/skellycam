import asyncio
import json
from asyncio import Task
from typing import Optional

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import WebsocketRequest

controller = get_or_create_controller()


class WebSocketConnectionManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.active = True
        self._should_continue = True
        self._ping_task: Optional[Task] = None
        self._pong_received = False

    async def accept_connection(self):
        await self.websocket.accept()
        self._ping_task = asyncio.create_task(self.send_pings())

    async def receive_and_process_messages(self):
        try:
            while self._should_continue:
                json_data = await self.websocket.receive_text()
                try:
                    websocket_request = WebsocketRequest.parse_raw(json_data)
                except ValidationError as e:
                    await self.websocket.send_text(f"Invalid request: {e.json()}")
                    continue

                if websocket_request.command == "get_frames":
                    await self.send_latest_frames()
                elif websocket_request.command == "pong":
                    logger.trace(f"Pong received!")
                    self._pong_received = True
                else:
                    await self.websocket.send_text("Unsupported request.")
        except WebSocketDisconnect:
            self.active = False
            logger.info("WebSocket Client disconnected")
        finally:
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()
            await self.websocket.close()

    async def send_latest_frames(self):
        try:
            latest_multi_frame_payload = (
                controller.camera_group_manager.get_latest_frames()
            )
            await self.websocket.send_bytes(latest_multi_frame_payload.to_bytes())
        except Exception as exc:
            logger.error(f"Error obtaining latest frames: {exc}")
            await self.websocket.send_text("Error obtaining latest frames.")

    async def send_pings(self):
        wait_for_pong_seconds = 3.0
        while self.active:
            try:
                self.pong_received = False
                await self.websocket.send_text(WebsocketRequest.ping())
                await asyncio.sleep(wait_for_pong_seconds)
                if not self.pong_received:
                    logger.info(
                        f"Ping message did not return Pong message within {wait_for_pong_seconds} - Shutting down..."
                    )
                    self._should_continue = False
            except WebSocketDisconnect:
                self.active = False
