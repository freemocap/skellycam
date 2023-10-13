import traceback

from skellycam import logger
from skellycam.backend.controller.core_functions.device_detection.detect_available_cameras import \
    detect_available_cameras
from skellycam.data_models.request_response_update import Request, Response, MessageType, EventTypes

CONTROLLER = None


def get_or_create_controller():
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER


class Controller:
    def handle_request(self, request: Request) -> Response:
        logger.debug(f"Controller received request:\n {request}")
        response = None
        try:
            match request.data["event"]:
                case "session_started":
                    logger.debug(f"Handling `session_started` event...")
                    cameras = detect_available_cameras()
                    logger.debug(f"Detected available cameras: {[camera.description for camera in cameras.values()]}")
                    response = Response(success=True,
                                        data={"cameras": cameras},
                                        event=EventTypes.CAMERA_DETECTED)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.exception(e)
            response = Response(success=False,
                                message_type=MessageType.ERROR,
                                data={"error": str(e),
                                      "traceback": traceback.format_exc()})
        finally:
            if response is None:
                response = Response(sucess=False,
                                    data={"message": "No response was generated!"})
            logger.debug(f"Controller generated response: response.success = {response.success}")

        return response
