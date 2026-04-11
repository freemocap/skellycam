import asyncio
import json
import logging

from fastapi import FastAPI
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellycam.api.websocket.websocket_messages import (
    WebsocketFrameAcknowledgement,
)
from skellycam.api.websocket.websocket_relay_handler import WebsocketRelayHandler
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager

logger = logging.getLogger(__name__)


class WebsocketServer:
    def __init__(self, app: FastAPI, websocket: WebSocket):
        self.websocket = websocket
        self.global_kill_flag = app.state.global_kill_flag
        self._cgm: CameraGroupManager = get_or_create_camera_group_manager(app=app)

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []

        self._send_lock = asyncio.Lock()

        self._relay_handler = WebsocketRelayHandler(
            cgm=self._cgm,
            send_bytes=self._send_bytes,
            send_json=self._send_json,
            send_text=self._send_text,
            should_continue_fn=lambda: self.should_continue,
            signal_shutdown_fn=self._signal_shutdown,
            global_kill_flag=self.global_kill_flag,
        )

    async def __aenter__(self):
        logger.debug("Entering WebsocketServer context manager...")
        self._websocket_should_continue = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketServer context manager exiting...")
        self._websocket_should_continue = False
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.close()
        for task in self.ws_tasks:
            if not task.done():
                task.cancel()
        logger.debug("WebsocketServer context manager exited.")

    @property
    def should_continue(self) -> bool:
        return (
            not self.global_kill_flag.value
            and self._websocket_should_continue
            and self.websocket.client_state == WebSocketState.CONNECTED
        )

    def _signal_shutdown(self) -> None:
        self._websocket_should_continue = False
        for task in self.ws_tasks:
            if not task.done():
                task.cancel()

    async def _send_json(self, data: dict) -> None:
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(data)

    async def _send_bytes(self, data: bytes) -> None:
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_bytes(data)

    async def _send_text(self, data: str) -> None:
        async with self._send_lock:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(data)

    async def run(self):
        logger.info("Starting WebSocket server...")
        self.ws_tasks = [
            asyncio.create_task(self._relay_handler.frontend_image_relay(), name="WsFrontendImageRelay"),
            asyncio.create_task(self._relay_handler.logs_relay(), name="WsLogsRelay"),
            asyncio.create_task(self._client_message_handler(), name="WsClientMessageHandler"),
            asyncio.create_task(self._relay_handler.app_state_sender(), name="WsStateSender"),
        ]
        try:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.debug("WebSocket server cancelled")
        except Exception as e:
            logger.exception(f"Error in WebSocket server: {e.__class__}: {e}")
            raise
        finally:
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()

    async def _client_message_handler(self):
        """Handle messages from the client — frame acks and ping/pong."""
        logger.info("Starting client message handler...")
        try:
            while self.should_continue:
                message = await self.websocket.receive()
                message_type: str = message.get("type", "")

                if message_type == "websocket.disconnect":
                    logger.info(f"Client disconnected (code={message.get('code', 'unknown')}), shutting down...")
                    self._signal_shutdown()
                    return

                if "text" in message:
                    text_content: str = message["text"]
                    if text_content.strip().startswith("{"):
                        try:
                            data = json.loads(text_content)
                        except json.JSONDecodeError as e:
                            raise ValueError(f"Failed to decode JSON: {e}") from e

                        msg_type = data.get("type", "")

                        if msg_type == "frame_ack" or "frameNumber" in data:
                            if "frameNumber" in data:
                                self._relay_handler.update_ack(
                                    frame_number=data["frameNumber"],
                                    display_image_sizes=data.get("displayImageSizes", None),
                                )
                            else:
                                ack = WebsocketFrameAcknowledgement.model_validate(data)
                                self._relay_handler.update_ack(
                                    frame_number=ack.frame_number,
                                    display_image_sizes=ack.display_image_sizes,
                                )
                        else:
                            logger.warning(f"Unknown WebSocket message type '{msg_type}' — commands are now handled via HTTP")
                    else:
                        if text_content.strip() == "ping":
                            await self._send_text("pong")
                        elif text_content.strip() == "pong":
                            pass
                        else:
                            logger.info(f"WebSocket received message: `{text_content}`")
                elif "bytes" in message:
                    logger.trace(f"Received binary WebSocket message ({len(message['bytes'])} bytes)")
                else:
                    raise RuntimeError(f"Unexpected ASGI WebSocket message: {message}")

        except WebSocketDisconnect:
            logger.info("Client disconnected (WebSocketDisconnect), shutting down...")
        except asyncio.CancelledError:
            logger.debug("Client message handler task cancelled")
        except Exception as e:
            logger.exception(f"Error handling client message: {e.__class__}: {e}")
            self.global_kill_flag.value = True
            raise
        finally:
            self._signal_shutdown()
            logger.info("Ending client message handler...")
