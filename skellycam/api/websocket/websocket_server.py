import asyncio
import json
import logging
import multiprocessing

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, get_skellycam_app
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import LogRecordModel, \
    get_websocket_log_queue
from skellycam.utilities.wait_functions import async_wait_1ms, async_wait_10ms

logger = logging.getLogger(__name__)


class WebsocketServer:
    def __init__(self, websocket: WebSocket):

        self.websocket = websocket
        self._app: SkellycamApplication = get_skellycam_app()

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []
        self.last_received_frontend_confirmation: int = -1
        self.last_sent_frame_number: int = -1

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        self._websocket_should_continue = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner context manager exiting...")
        self._websocket_should_continue = False

        # Only close if still connected
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.close()
        # Cancel all tasks
        for task in self.ws_tasks:
            if not task.done():
                task.cancel()
        logger.debug("WebsocketRunner context manager exited.")

    @property
    def should_continue(self):
        return (
                self._app.should_continue
                and self._websocket_should_continue
                and self.websocket.client_state == WebSocketState.CONNECTED
        )

    async def run(self):
        logger.info("Starting websocket runner...")
        self.ws_tasks = [asyncio.create_task(self._frontend_image_relay(), name="WebsocketFrontendImageRelay"),
                         # asyncio.create_task(self._ipc_queue_relay(), name="WebsocketIPCQueueRelay"),
                         asyncio.create_task(self._logs_relay(), name="WebsocketLogsRelay"),
                         asyncio.create_task(self._client_message_handler(), name="WebsocketClientMessageHandler")]

        try:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            # Cancel all tasks when exiting
            for task in self.ws_tasks:
                if not task.done():
                    task.cancel()
            raise

    async def _frontend_image_relay(self):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info(
            f"Starting frontend image payload relay...")
        try:
            while self.should_continue:
                await async_wait_10ms()
                if  self.last_received_frontend_confirmation >= self.last_sent_frame_number:

                    new_frontend_payloads: list[FrontendFramePayload] = self._app.get_new_frontend_payloads(
                        if_newer_than=self.last_sent_frame_number)
                    for fe_payload in new_frontend_payloads:
                        if not self.websocket.client_state == WebSocketState.CONNECTED:
                            logger.error("Websocket is not connected, cannot send payload!")
                            raise RuntimeError("Websocket is not connected, cannot send payload!")

                        if self.websocket.client_state != WebSocketState.CONNECTED:
                            return

                        payload_json = fe_payload.model_dump_json()
                        payload_bytes = payload_json.encode('utf-8')
                        # if fe_payload.multi_frame_number %2 == 0:
                        #     continue
                        await self.websocket.send_bytes(payload_bytes)
                        self.last_sent_frame_number = fe_payload.multi_frame_number
        except WebSocketDisconnect:
            logger.api("Client disconnected, ending Frontend Image relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            get_skellycam_app().kill_everything()
            raise

    async def _logs_relay(self):
        logger.info("Starting websocket log relay listener...")
        logs_queue = get_websocket_log_queue()
        try:
            while self.should_continue:
                if not logs_queue.empty() or self.websocket.client_state != WebSocketState.CONNECTED:
                    try:
                        log_record: LogRecordModel = logs_queue.get_nowait()
                        # await self.websocket.send_json(log_record)
                    except (multiprocessing.queues.Empty, logs_queue.Empty):
                        await async_wait_1ms()
                else:
                    await async_wait_10ms()

        except asyncio.CancelledError:
            logger.debug("Log relay task cancelled")

    async def _client_message_handler(self):
        """
        Handle messages from the client.
        """
        logger.info("Starting client message handler...")
        try:
            while self.should_continue:
                try:
                    message = await self.websocket.receive()
                    if message:
                        if "text" in message:
                            text_content = message.get("text", "")
                            # Try to parse as JSON if it looks like JSON
                            if text_content.strip().startswith('{') or text_content.strip().startswith('['):
                                try:
                                    data = json.loads(text_content)

                                    # Handle received_frame acknowledgment
                                    if 'multi_frame_number' in data:
                                        self.last_received_frontend_confirmation = data['multi_frame_number']

                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to decode JSON message: {e}")
                            else:
                                # Handle plain text messages
                                logger.info(f"Websocket received message: `{text_content}`")
                                # Add any specific handling for plain text commands here

                        elif "bytes" in message:
                            bytes_content = message.get("bytes", b"")
                            logger.debug(f"Received bytes message of length {len(bytes_content)}")
                            try:
                                # Attempt to decode bytes as JSON
                                text_content = bytes_content.decode('utf-8')
                                if text_content.strip().startswith('{') or text_content.strip().startswith('['):
                                    data = json.loads(text_content)
                                    logger.info(f"Processed JSON message from client: {data}")

                                    # Handle received_frame acknowledgment
                                    if 'received_frame' in data:
                                        self.last_received_frontend_confirmation = data['received_frame']
                                        logger.debug(
                                            f"Frontend acknowledged receipt of frame {self.last_received_frontend_confirmation}")
                            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                                logger.error(f"Failed to decode bytes message: {e}")

                        else:
                            logger.warning(f"Received unexpected message format: {message}")

                except WebSocketDisconnect:
                    logger.info("Client disconnected, ending client message handler...")
                    self._websocket_should_continue = False
                    break
                except Exception as e:
                    logger.exception(f"Error handling client message: {e.__class__}: {e}")
        except asyncio.CancelledError:
            logger.debug("Client message handler task cancelled")
        finally:
            logger.info("Ending client message handler...")
