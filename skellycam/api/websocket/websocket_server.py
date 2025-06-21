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
        self.last_received_frontend_confirmation: int | None = None
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
        latest_mf_number: int | None = None
        try:
            while self.should_continue:
                await async_wait_1ms()
                if self.last_received_frontend_confirmation is None or self.last_received_frontend_confirmation >= latest_mf_number:

                    new_frontend_payloads: list[FrontendFramePayload]  = self._app.get_new_frontend_payloads(if_newer_than=latest_mf_number)
                    for fe_payload in new_frontend_payloads:
                        latest_mf_number = fe_payload.multi_frame_number
                        if not self.websocket.client_state == WebSocketState.CONNECTED:
                            logger.error("Websocket is not connected, cannot send payload!")
                            raise RuntimeError("Websocket is not connected, cannot send payload!")

                        if self.websocket.client_state != WebSocketState.CONNECTED:
                            return

                        payload_json = fe_payload.model_dump_json()
                        payload_bytes = payload_json.encode('utf-8')
                        await self.websocket.send_bytes(payload_bytes)
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
                    message = await self.websocket.receive_json()
                    data = json.loads(message)
                    logger.info(f"Received message from client: {data}")

                    # Handle received_frame acknowledgment
                    if 'received_frame' in data:
                        self.last_received_frontend_confirmation = data['received_frame']
                        logger.debug(f"Frontend acknowledged receipt of frame {self.last_received_frontend_confirmation}")

                except WebSocketDisconnect:
                    logger.api("Client disconnected, ending client message handler...")
                    break
                except Exception as e:
                    logger.exception(f"Error handling client message: {e.__class__}: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Ending client message handler...")