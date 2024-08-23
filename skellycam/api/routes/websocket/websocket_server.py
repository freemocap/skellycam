import asyncio
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from skellycam.api.app.app_state import AppState, get_app_state
from skellycam.api.routes.websocket.ipc import get_frontend_ws_relay_frame_pipe, get_ipc_queue

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

HELLO_CLIENT_TEXT_MESSAGE = "👋Hello, websocket client!"
HELLO_CLIENT_BYTES_MESSAGE = b"Beep boop - hi im bytes wow"
HELLO_CLIENT_JSON_MESSAGE = {"message": "hey wow im json!"}

FRONTEND_READY_FOR_NEXT_PAYLOAD_TEXT = "frontend_ready_for_next_payload"
CLOSE_WEBSOCKET_MESSAGE = "close_websocket"


async def listen_for_client_messages(websocket: WebSocket):
    logger.info("Starting listener for client messages...")
    while True:
        try:
            message = await websocket.receive_text()
            logger.loop(f"Message from client: '{message}'")

        except WebSocketDisconnect:
            logger.api("Client disconnected, ending listener task...")
            break
        except Exception as e:
            logger.error(f"Error while receiving message: {type(e).__name__} - {e}")
            break


async def websocket_relay(websocket: WebSocket):
    """
    Relay messages from the sub-processes to the frontend via the websocket.
    """
    logger.info("Starting websocket relay listener...")
    frontend_frame_pipe = get_frontend_ws_relay_frame_pipe()  # Receives frame payloads and recording info (bytes only)
    ipc_queue = get_ipc_queue()  # Receives messages the sub-processes
    app_state = get_app_state()
    try:
        while True:
            if frontend_frame_pipe.poll():
                payload: bytes = frontend_frame_pipe.recv_bytes()

                logger.loop(
                    f"Relay bytes payload through websocket, size:  {len(payload) * .001:.3f}kB")

                await websocket.send_bytes(payload)

            if not ipc_queue.empty():
                message = ipc_queue.get()
                logger.trace(f"Relaying message from sub-process: {message}")
                if isinstance(message, AppState):
                    app_state.update_state(message)
                    await websocket.send_json(message.state().model_dump_json())
            else:
                await asyncio.sleep(0.001)
    except WebSocketDisconnect:
        logger.api("Client disconnected, ending listener task...")
    finally:
        logger.info("Ending listener for frontend payload messages in queue...")

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

    await websocket.accept()
    await websocket.send_text(HELLO_CLIENT_TEXT_MESSAGE)
    await websocket.send_bytes(HELLO_CLIENT_BYTES_MESSAGE)
    await websocket.send_json(HELLO_CLIENT_JSON_MESSAGE)
    logger.success(f"Websocket connection established!")

    async with WebsocketRunner():
        try:
            logger.api("Creating listener task...")
            listener_task = listen_for_client_messages(websocket=websocket)
            relay_task = websocket_relay(websocket=websocket)
            await asyncio.gather(listener_task, relay_task)
        except WebSocketDisconnect:
            logger.info("Client disconnected")

        finally:
            if not websocket.client_state == WebSocketState.DISCONNECTED:
                await websocket.send_text("Goodbye, client👋")
                await websocket.close()
            logger.info("Websocket closed")
