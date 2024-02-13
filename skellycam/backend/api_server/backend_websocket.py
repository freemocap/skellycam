import asyncio
import time

from starlette.websockets import WebSocket

from skellycam.backend.controller.controller import get_or_create_controller

import logging

logger = logging.getLogger(__name__)

controller = get_or_create_controller()


class BackendWebsocketManager:
    """
    A class to manage the connection to the BACKEND websocket server.
    This connection has one purpose: to receive requests from the frontend and respond with the latest frames via MultiFramePayload.to_bytes().
    Other communication happens through the REST API.
    """

    def __init__(
        self, websocket: WebSocket, shutdown_event: asyncio.Event, timeout: float
    ):
        self.websocket = websocket
        self._shutdown_event = shutdown_event
        self._should_continue = True
        self._time_since_last_message = 0
        self._max_time_since_last_message = timeout

    async def accept_connection(self):
        logger.debug("Awaiting websocket connection...")
        await self.websocket.accept()
        logger.info("WebSocket Backend client connected!")
        keepalive_task = asyncio.create_task(self.keepalive_handler())
        await self.receive_and_process_messages()
        await keepalive_task

    def shut_down(self):
        logger.info("Shutting down WebSocket Backend client...")
        self._should_continue = False

    async def receive_and_process_messages(self):
        previous_message_time = (
            time.perf_counter()
        )  # dummy time to initialize the variable before the first message

        try:
            while self._should_continue:
                incoming_bytes = await self.websocket.receive_bytes()

                current_message_time = time.perf_counter()
                self._time_since_last_message = (
                    current_message_time - previous_message_time
                )
                previous_message_time = current_message_time

                logger.debug(f"Received bytes: {incoming_bytes}")
                await self.websocket.send_bytes(
                    bytes(f"received bytes: {incoming_bytes}", "utf-8")
                )

                if incoming_bytes == b"give-frames-plz":
                    await self.send_latest_frames()

        except Exception as e:
            logger.info(f"Exception in receive_and_process_messages: {e}")
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

    async def keepalive_handler(self):
        while self._should_continue:
            try:
                if self._shutdown_event.is_set():
                    self._should_continue = False
                    await self.websocket.close()
                    logger.info(
                        "WebSocket connection closed due to the `shutdown` event being set."
                    )
                    break

                if self._time_since_last_message > self._max_time_since_last_message:
                    raise asyncio.TimeoutError
                await asyncio.sleep(1)

            except asyncio.TimeoutError:
                self._should_continue = False  # This will stop the main loop as well
                await self.websocket.close()
                logger.error("WebSocket connection closed due to timeout.")
