import asyncio
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from skellycam.api.app.app_state import SubProcessStatus, AppStateDTO, get_app_state
from skellycam.api.routes.websocket.ipc import get_frontend_ws_relay_pipe, get_ipc_queue

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

HELLO_CLIENT_TEXT_MESSAGE = "👋Hello, websocket client!"
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
    frontend_frame_pipe = get_frontend_ws_relay_pipe()  # Receives frames from the sub-processes (bytes only!)
    ipc_queue = get_ipc_queue()  # Receives messages the sub-processes
    app_state = get_app_state()
    try:
        while True:
            if frontend_frame_pipe.poll():
                payload: bytes = frontend_frame_pipe.recv_bytes()
                logger.loop(f"Relaying payload to frontend: {len(payload)} bytes")
                await websocket.send_bytes(payload)

            if not ipc_queue.empty():
                message = ipc_queue.get()
                if isinstance(message, AppStateDTO):
                    logger.trace(f"Relaying AppStateDTO to frontend")
                    await websocket.send_json(message.model_dump_json())
                    # await websocket.send_json(message.model_dump_json())
                elif isinstance(message, SubProcessStatus):
                    pass
                    # app_state.update_process_status(message)
                else:
                    raise ValueError(f"Unknown message type: {type(message)}")
            else:
                await asyncio.sleep(0.001)
    except WebSocketDisconnect:
        logger.api("Client disconnected, ending listener task...")
    except Exception as e:
        logger.exception(f"Error in websocket relay: {e.__class__}: {e}")
        raise
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
