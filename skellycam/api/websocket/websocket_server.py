import asyncio
import json
import logging
import multiprocessing
import time

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.frame_payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frame_payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.recorders.timestamps.framerate_tracker import CurrentFramerate, FramerateTracker
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, get_skellycam_app, SkellycamAppStateDTO
from skellycam.system.logging_configuration.handlers.websocket_log_queue_handler import LogRecordModel
from skellycam.utilities.wait_functions import async_wait_1ms, async_wait_10ms

logger = logging.getLogger(__name__)


class WebsocketServer:
    def __init__(self, websocket: WebSocket):

        self.websocket = websocket
        self._app: SkellycamApplication = get_skellycam_app()

        self.latest_backend_framerate: CurrentFramerate | None = None
        self.latest_frontend_framerate: CurrentFramerate | None = None

        self._websocket_should_continue = True
        self.ws_tasks: list[asyncio.Task] = []

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

        if not self._app.ipc.global_kill_flag.value:
            logger.error("Websocket connection closed, but global kill flag is not set. "
                         "This indicates a potential issue with the application state."
                         )

    @property
    def should_continue(self):
        return (
                self._app.ipc.global_should_continue
                and self._websocket_should_continue
                and self.websocket.client_state == WebSocketState.CONNECTED
        )

    async def run(self):
        logger.info("Starting websocket runner...")
        self.ws_tasks = [asyncio.create_task(self._frontend_image_relay(), name="WebsocketFrontendImageRelay"),
                         asyncio.create_task(self._ipc_queue_relay(), name="WebsocketIPCQueueRelay"),
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

    async def _ipc_queue_relay(self):
        """
        Relay messages from the sub-processes to the frontend via the websocket.
        """
        logger.info("Starting websocket relay listener...")

        try:
            while self.should_continue:
                if not self._app.ipc.ws_ipc_relay_queue.empty():
                    try:
                        await self._handle_ipc_queue_message(message=self._app.ipc.ws_ipc_relay_queue.get())
                    except multiprocessing.queues.Empty:
                        continue
                    except Exception as e:
                        logger.exception(f"Error handling IPC queue message: {e.__class__}: {e}")
                        raise
                else:
                    await async_wait_1ms()

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Ending listener for frontend payload messages in queue...")
        logger.info("Ending listener for client messages...")

    async def _handle_ipc_queue_message(self, message: object | None = None):
        if isinstance(message, SkellycamAppStateDTO):
            logger.trace(f"Relaying SkellycamAppStateDTO to frontend")
        elif isinstance(message, dict) and isinstance(list(message.values())[0], CameraConfig):
            logger.trace(f"Updating device extracted camera configs")
            self._app.set_device_extracted_camera_configs(message)
            return
        elif isinstance(message, CurrentFramerate):
            self.latest_backend_framerate = message
            return  # will send framerate update bundled with frontend payload
        else:
            logger.warning(f"Unknown message type: {type(message)}")

        await self.websocket.send_json(message.model_dump())

    async def _frontend_image_relay(self):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info(
            f"Starting frontend image payload relay...")
        frontend_framerate_tracker = FramerateTracker.create(framerate_source="frontend")
        camera_group_uuid = None
        latest_mf_number = -1
        try:
            while self.should_continue:
                await async_wait_1ms()

                if not self._app.frame_escape_shm:
                    latest_mf_number = -1
                    continue

                if self._app.camera_group and camera_group_uuid != self._app.camera_group.uuid:
                    latest_mf_number = -1
                    camera_group_uuid = self._app.camera_group.uuid
                    continue

                if not self._app.frame_escape_shm.latest_mf_number.value > latest_mf_number:
                    continue

                mf_payload = self._app.frame_escape_shm.get_multi_frame_payload(
                    camera_configs=self._app.camera_group.camera_configs,
                    retrieve_type="latest")
                frontend_framerate_tracker.update(time.perf_counter_ns())
                if mf_payload.multi_frame_number % 10 == 0:
                    # update every 10 multi-frames to match backend framerate behavior
                    self.latest_frontend_framerate = frontend_framerate_tracker.current_framerate
                await self._send_frontend_payload(mf_payload)
                latest_mf_number = mf_payload.multi_frame_number

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending Frontend Image relay task...")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            raise

    async def _send_frontend_payload(self,
                                     mf_payload: MultiFramePayload):
        mf_payload.backend_framerate = self.latest_backend_framerate
        mf_payload.frontend_framerate = self.latest_frontend_framerate
        frontend_payload = FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf_payload)
        logger.loop(f"Sending frontend payload through websocket...")
        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket is not connected, cannot send payload!")
            raise RuntimeError("Websocket is not connected, cannot send payload!")

        if self.websocket.client_state != WebSocketState.CONNECTED:
            return

        await self.websocket.send_bytes(frontend_payload.model_dump_json().encode('utf-8'))

        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket shut down while sending payload!")
            raise RuntimeError("Websocket shut down while sending payload!")

    async def _logs_relay(self):
        logger.info("Starting websocket log relay listener...")
        try:
            while self.should_continue:
                if not self._app.ipc.ws_logs_queue.empty() or self.websocket.client_state != WebSocketState.CONNECTED:
                    try:
                        log_record: LogRecordModel = self._app.ipc.ws_logs_queue.get_nowait()
                        await self.websocket.send_json(log_record)
                    except (multiprocessing.queues.Empty, self._app.ipc.ws_logs_queue.Empty):
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
                    message = await self.websocket.receive_text()
                    data = json.loads(message)
                    logger.info(f"Received message from client: {data}")
                except WebSocketDisconnect:
                    logger.api("Client disconnected, ending client message handler...")
                    break
                except Exception as e:
                    logger.exception(f"Error handling client message: {e.__class__}: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Ending client message handler...")
