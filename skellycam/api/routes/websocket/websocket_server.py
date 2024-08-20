import asyncio
import logging
import multiprocessing
import time

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from skellycam.core.controller import get_controller
from skellycam.core.frames.payload_models.frontend_image_payload import FrontendFramePayload

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

HELLO_CLIENT_TEXT_MESSAGE = "👋Hello, websocket client!"
HELLO_CLIENT_BYTES_MESSAGE = b"Beep boop - these are bytes from the websocket server wow"
HELLO_CLIENT_JSON_MESSAGE = {"message": HELLO_CLIENT_TEXT_MESSAGE + " I'm a JSON message!"}


async def listen_for_client_messages(websocket: WebSocket):
    logger.info("Starting listener for client messages...")
    while True:
        try:
            message = await websocket.receive_text()
            logger.debug(f"Message from client: '{message}'")

            # if not message:
            #     logger.api("Empty message received, ending listener task...")
            #     get_client().shutdown_server()
            #     break
        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
            break
        except Exception as e:
            logger.error(f"Error while receiving message: {type(e).__name__} - {e}")
            break


async def relay_messages_from_queue_to_client(websocket: WebSocket, frontend_payload_queue: multiprocessing.Queue):
    logger.info("Starting listener for frontend payload messages in queue...")
    while True:
        try:
            if not frontend_payload_queue.empty():
                fe_payload: FrontendFramePayload = frontend_payload_queue.get()
                if not fe_payload:
                    logger.api("Received empty payload, ending listener task...")
                    break
                logger.loop(
                    f"Pulled front-end payload from fe_queue and sending down `websocket` to client: {fe_payload}")
                fe_payload.lifespan_timestamps_ns.append({"sent_down_websocket": time.perf_counter_ns()})
                await websocket.send_json(fe_payload.model_dump())
            else:
                await asyncio.sleep(0.001)
        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")

    logger.info("Ending listener for client messages...")


class WebsocketRunner:
    async def __aenter__(self):
        logger.debug("WebsocketRunner started...")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("WebsocketRunner ended...")
        pass


@websocket_router.websocket("/connect")
async def websocket_server_connect(websocket: WebSocket):
    """
    Websocket endpoint for client connection to the server - handles image data streaming to frontend.
    """
    frontend_payload_queue = multiprocessing.Queue()
    get_controller().set_frontend_payload_queue(fe_queue=frontend_payload_queue)

    await websocket.accept()
    await websocket.send_text(HELLO_CLIENT_TEXT_MESSAGE)
    await websocket.send_bytes(HELLO_CLIENT_BYTES_MESSAGE)
    await websocket.send_json(HELLO_CLIENT_JSON_MESSAGE)
    logger.success(f"Websocket connection established!")

    async with WebsocketRunner():
        try:
            logger.api("Creating listener task...")
            listener_task = listen_for_client_messages(websocket)
            relay_task = relay_messages_from_queue_to_client(websocket=websocket,
                                                             frontend_payload_queue=frontend_payload_queue)
            await asyncio.gather(listener_task, relay_task)
        except WebSocketDisconnect:
            logger.info("Client disconnected")
        except Exception as e:
            logger.exception(e)
            logger.error(f"Error while running camera loop: {type(e).__name__}- {e}")
        finally:
            if not websocket.client_state == WebSocketState.DISCONNECTED:
                await websocket.send_text("Goodbye, client👋")
                await websocket.close()
            logger.info("Websocket closed")
