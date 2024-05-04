import logging

from skellycam.backend.core.controller.controller import Controller

logger = logging.getLogger(__name__)

CONTROLLER = None


def get_controller():
    global CONTROLLER
    if CONTROLLER is None:
        raise ValueError("Controller not yet initialized!")
    logger.debug(f"Getting controller: {CONTROLLER}")
    return CONTROLLER


def set_controller(controller: Controller):
    global CONTROLLER
    CONTROLLER = controller
    logger.debug(f"Set controller to {CONTROLLER}")
