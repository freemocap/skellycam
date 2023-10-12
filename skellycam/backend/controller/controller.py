from skellycam import logger
from skellycam.data_models.request_response_update import Request, Response

CONTROLLER = None


def get_or_create_controller():
    global CONTROLLER
    if CONTROLLER is None:
        CONTROLLER = Controller()
    return CONTROLLER

class Controller:
    def handle_request(self, request: Request):
        logger.info(f"Controller received request:\n {request}")
        return Response(sucess=True,
                        data=request.dict())


