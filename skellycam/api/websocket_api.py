from fastapi import HTTPException
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from skellycam.backend.controller.controller import get_or_create_controller
from skellycam.frontend.gui.skellycam_widget.manager.helpers.frame_grabber import (
    GetFramesRequest,
)

controller = get_or_create_controller()


async def camera_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint to connect to the SkellyCam API.
    When a client sends a message that says "get_frames", the server responds by sending the latest frames.
    """
    await websocket.accept()  # Accept the WebSocket connection
    try:
        while True:
            json_data = await websocket.receive_text()
            try:
                # Attempt to parse the JSON data and validate it against the Pydantic model
                get_frames_request = GetFramesRequest.parse_raw(json_data)
            except ValidationError as e:
                # Send back a message if there's a validation error
                await websocket.send_text(f"Invalid request: {e.json()}")
                continue

            if get_frames_request.command == "get_frames":
                try:
                    latest_multi_frame_payload = (
                        controller.camera_group_manager.get_latest_frames()
                    )

                    await websocket.send_bytes(latest_multi_frame_payload.to_bytes())
                except Exception as exc:
                    print(f"Error obtaining latest frames: {exc}")
                    await websocket.send_text("Error obtaining latest frames.")
                    raise HTTPException(status_code=500, detail=str(exc))
            else:
                # Optionally handle other messages or send an error/warning to the client
                await websocket.send_text("Unsupported request.")
    except WebSocketDisconnect:
        print("Websocket Client disconnected")
    except Exception as e:
        # Handle other connection errors, e.g., log or send an error message
        print(f"Error in WebSocket connection: {e}")
    finally:
        # Ensure the connection is closed properly
        await websocket.close()
