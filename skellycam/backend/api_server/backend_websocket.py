import asyncio
import logging
import time

from starlette.websockets import WebSocket

from skellycam.backend.controller.controller import get_or_create_controller

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
        self._most_recent_message_timestamp = None

    async def accept_connection(self):
        logger.debug("Awaiting websocket connection...")
        await self.websocket.accept()
        logger.info("WebSocket Backend client connected!")
        await self.receive_and_process_text_messages()
        keepalive_task = asyncio.create_task(self.keepalive_handler())
        await keepalive_task

    def shut_down(self):
        logger.info("Shutting down WebSocket Backend client...")
        self._should_continue = False

    async def receive_and_process_text_messages(self):
        logger.debug("Starting to receive and process messages...")
        self._most_recent_message_timestamp = time.perf_counter()

        try:
            while self._should_continue:
                incoming_message: str = await self.websocket.receive_text()
                logger.trace(f"Received message: {incoming_message}")

                self._most_recent_message_timestamp = time.perf_counter()

                if incoming_message == "Ping!":
                    logger.info("Received ping from client.")
                    await self.websocket.send_text("Pong!")

        except Exception as e:
            logger.info(f"Exception in receive_and_process_messages: {e}")
        finally:
            await self.websocket.close()

    async def send_latest_frames(self):
        logger.trace("Sending latest frames...")
        try:
            latest_multi_frame_payload = (
                controller.camera_group_manager.get_latest_frames()
            )
            if latest_multi_frame_payload is None:
                logger.trace("No frames to send - returning nothing.")
                pass
            else:
                await self.websocket.send_bytes(latest_multi_frame_payload.to_bytes())
        except Exception as e:
            logger.error(f"Error obtaining latest frames: {e}")
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

                time_since_last_message = (
                    time.perf_counter() - self._most_recent_message_timestamp
                )
                if time_since_last_message > self._max_time_since_last_message:
                    logger.error(
                        f"WebSocket connection closed due to timeout of {self._max_time_since_last_message} seconds."
                    )
                    raise asyncio.TimeoutError

                await asyncio.sleep(1)

            except asyncio.TimeoutError:
                self._should_continue = False  # This will stop the main loop as well
                await self.websocket.close()
                logger.error("WebSocket connection closed due to timeout.")

        logger.info("WebSocket connection `keepalive_handler` finished.")
