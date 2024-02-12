import json

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from skellycam.backend.controller.controller import get_or_create_controller
import logging

controller = get_or_create_controller()


class BackendWebsocketConnectionManager:
    """
    A class to manage the connection to the BACKEND websocket server.
    This connection has one purpose: to receive requests from the frontend and respond with the latest frames via MultiFramePayload.to_bytes().
    Other communication happens through the REST API.
    """

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._should_continue = True

    async def accept_connection(self):
        logger.debug("Awaiting websocket connection...")
        await self.websocket.accept()
        logger.info("WebSocket Backend client connected!")

    async def receive_and_process_messages(self):
        try:
            while self._should_continue:
                incoming_bytes = await self.websocket.receive_bytes()
                logger.debug(f"Received bytes: {incoming_bytes}")
                await self.websocket.send_bytes(
                    bytes(f"received bytes: {incoming_bytes}", "utf-8")
                )

                if incoming_bytes == b"give-frames-plz":
                    await self.send_latest_frames()

        except WebSocketDisconnect:
            logger.info("WebSocket Client disconnected")
        finally:
            await self.websocket.close()

    async def send_latest_frames(self):
        try:
            latest_multi_frame_payload = (
                controller.camera_group_manager.get_latest_frames()
            )
            if latest_multi_frame_payload is None:
                pass
            else:
                await self.websocket.send_bytes(latest_multi_frame_payload.to_bytes())
        except Exception as exc:
            logger.error(f"Error obtaining latest frames: {exc}")
            await self.websocket.send_text("Error obtaining latest frames.")
