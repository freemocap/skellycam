import asyncio
import json
import time
from asyncio import Task
from typing import Optional

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.backend.system.environment.get_logger import logger
from skellycam.frontend.api_client.frontend_websocket import BaseWebsocketRequest

controller = get_or_create_controller()


class WebSocketConnectionManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.active = True
        self._should_continue = True

    async def accept_connection(self):
        await self.websocket.accept()

    async def receive_and_process_messages(self):
        try:
            while self._should_continue:
                incoming_json_data = await self.websocket.receive_text()

                try:
                    request: BaseWebsocketRequest = json.loads(incoming_json_data)
                except ValidationError as e:
                    await self.websocket.send_text(f"Invalid request: {e.json()}")
                    continue

                await self._handle_request(request)

        except WebSocketDisconnect:
            self.active = False
            logger.info("WebSocket Client disconnected")
        finally:
            await self.websocket.close()

    async def _handle_request(self, request: BaseWebsocketRequest):
        if request.command == "get_frames":
            await self.send_latest_frames()
        elif request.command == "ping":
            logger.trace(f"Pong received!")
            await self._send_pong_response()
        else:
            await self.websocket.send_text(f"Unsupported request: {request.command}")

    async def send_latest_frames(self):
        try:
            latest_multi_frame_payload = (
                controller.camera_group_manager.get_latest_frames()
            )
            await self.websocket.send_bytes(latest_multi_frame_payload.to_bytes())
        except Exception as exc:
            logger.error(f"Error obtaining latest frames: {exc}")
            await self.websocket.send_text("Error obtaining latest frames.")

    async def _send_pong_response(self):
        await self.websocket.send_text("pong")
