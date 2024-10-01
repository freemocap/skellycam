import asyncio
import json
import logging
import multiprocessing
from json import JSONDecodeError
from typing import Optional, Dict

from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from skellycam.api.app.app_state import AppStateDTO, SubProcessStatus
from skellycam.api.websocket.ipc import get_ipc_queue
from skellycam.core.frames.payloads.frontend_image_payload import FrontendFramePayload
from skellycam.core.frames.payloads.multi_frame_payload import MultiFramePayload
from skellycam.core.shmemory.camera_shared_memory_manager import CameraGroupSharedMemoryDTO, CameraGroupSharedMemory
from skellycam.core.timestamps.frame_rate_tracker import CurrentFrameRate
from skellycam.core.videos.video_recorder_manager import RecordingInfo
from skellycam.utilities.wait_functions import async_wait_1ms

logger = logging.getLogger(__name__)


class WebsocketServer:
    def __init__(self, websocket: WebSocket):
        self._first_frontend_images_sent = False
        self.websocket = websocket

        self.listen_for_client_messages_task: Optional[asyncio.Task] = None

        self.ipc_queue = get_ipc_queue()  # Receives messages the sub-processes
        self.frontend_image_relay_task: Optional[asyncio.Task] = None
        self.shutdown_relay_flag = asyncio.Event()
        self._frontend_image_sizes: Optional[Dict[str, int]]  = None

    async def __aenter__(self):
        logger.debug("Entering WebsocketRunner context manager...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner context manager exiting...")
        if not self.websocket.client_state == WebSocketState.DISCONNECTED:
            await self.websocket.close()

    async def run(self):
        logger.info("Starting websocket runner...")
        try:
            await asyncio.gather(
                asyncio.create_task(self._listen_for_client_messages()),
                asyncio.create_task(self._ipc_queue_relay()),
            )
        except Exception as e:
            logger.exception(f"Error in websocket runner: {e.__class__}: {e}")
            raise

    async def _ipc_queue_relay(self):
        """
        Relay messages from the sub-processes to the frontend via the websocket.
        """
        logger.info("Starting websocket relay listener...")

        try:
            while True:
                if self.ipc_queue.qsize() > 0:
                    try:
                        await self._handle_ipc_queue_message(message=self.ipc_queue.get())
                    except multiprocessing.queues.Empty:
                        continue
                else:
                    await async_wait_1ms()

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
        except Exception as e:
            logger.exception(f"Error in websocket relay: {e.__class__}: {e}")
            raise
        finally:
            logger.info("Ending listener for frontend payload messages in queue...")

        logger.info("Ending listener for client messages...")

    async def _handle_ipc_queue_message(self, message: Optional[object] = None):
        if isinstance(message, AppStateDTO):
            logger.trace(f"Relaying AppStateDTO to frontend")
            await self.websocket.send_json(message.model_dump_json())

        elif isinstance(message, CameraGroupSharedMemoryDTO):
            logger.debug(f"Received CameraGroupSharedMemoryDTO in websocket relay")
            if self.frontend_image_relay_task is not None:
                logger.debug("Received new GroupSharedMemoryNames - stopping previous relay task...")
                await self._shutdown_image_relay_task()
            self.frontend_image_relay_task = asyncio.create_task(
                self._frontend_image_relay(camera_group_shm_dto=message)
            )
        elif isinstance(message, SubProcessStatus):
            pass
            # app_state.update_process_status(message) # TODO - implement this or remove it
        elif isinstance(message, RecordingInfo):
            logger.trace(f"Relaying RecordingInfo to frontend")
            await self.websocket.send_json(message.model_dump_json())
        elif isinstance(message, CurrentFrameRate):
            logger.loop(f"Relaying CurrentFrameRate to frontend")
            await self.websocket.send_json(message.model_dump_json())
        else:
            raise ValueError(f"Unknown message type: {type(message)}")

    async def _frontend_image_relay(self,
                                    camera_group_shm_dto: CameraGroupSharedMemoryDTO):
        """
        Relay image payloads from the shared memory to the frontend via the websocket.
        """
        logger.info(
            f"Starting frontend image payload relay with shared memory names {camera_group_shm_dto.group_shm_names}...")
        camera_group_shm = CameraGroupSharedMemory.recreate(dto=camera_group_shm_dto)
        last_mf_number_read = camera_group_shm.multi_frame_number
        mf_payload: Optional[MultiFramePayload] = None
        try:
            while not self.shutdown_relay_flag.is_set():
                shm_mf_number = camera_group_shm.multi_frame_number
                if shm_mf_number == last_mf_number_read:
                    await async_wait_1ms()
                    continue
                logger.loop(f"New multi-frame number detected! last_mf_number_read: {last_mf_number_read}, shm_mf_number: {shm_mf_number}")
                last_mf_number_read = shm_mf_number


                mf_payload = camera_group_shm.get_multi_frame_payload(previous_payload=mf_payload,
                                                                      read_only=True)  # read-only so we don't increment the counter, that's the FrameListener's job
                await self._send_frontend_payload(mf_payload)

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
        except Exception as e:
            logger.exception(f"Error in image payload relay: {e.__class__}: {e}")
            raise
        finally:
            logger.info("Ending listener for frontend image payloads...")
            if self.frontend_image_relay_task is not None:
                await self._shutdown_image_relay_task()
            camera_group_shm.close()  # close, but do not unlink, the shared memory. SHM will be unlinked by the process that created it.

        logger.info("Ending listener for client messages...")

    async def _send_frontend_payload(self,
                                     mf_payload: MultiFramePayload):
        frontend_payload = FrontendFramePayload.from_multi_frame_payload(multi_frame_payload=mf_payload,
                                                                         image_sizes = self._frontend_image_sizes)
        logger.loop(f"Sending frontend payload through websocket...")
        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket is not connected, cannot send payload!")
            raise RuntimeError("Websocket is not connected, cannot send payload!")

        await self.websocket.send_bytes(frontend_payload.model_dump_json().encode('utf-8'))

        if not self.websocket.client_state == WebSocketState.CONNECTED:
            logger.error("Websocket shut down while sending payload!")
            raise RuntimeError("Websocket shut down while sending payload!")

        self._first_frontend_images_sent = True

    async def _shutdown_image_relay_task(self):
        self.shutdown_relay_flag.set()
        await self.frontend_image_relay_task
        self.shutdown_relay_flag.clear()

    async def _listen_for_client_messages(self):
        logger.info("Starting listener for client messages...")
        while True:
            try:
                message = await self.websocket.receive_json()
                logger.trace(f"Message from client: '{message}'")
                if not message:
                    logger.api("Client send empty message, closing websocket...")
                    await self.websocket.close()
                try:
                    data = json.loads(message)
                except JSONDecodeError:
                    raise RuntimeError("For simplicity, the websocket server only accepts JSON formatted messages")

                if "sizes" in data.keys() and  self._first_frontend_images_sent:
                    self._frontend_image_sizes = data["sizes"] #CameraViewSizes object

            except WebSocketDisconnect:
                logger.api("Client disconnected, ending listener task...")
                break
            except Exception as e:
                logger.error(f"Error while receiving message: {type(e).__name__} - {e}")
                break
