import logging

from skellycam.core.controller.controller import Controller

logger = logging.getLogger(__name__)

CONTROLLER = None


def get_or_create_controller():
    global CONTROLLER
    if CONTROLLER is None:
        logger.debug("Creating new controller...")
        CONTROLLER = Controller()
    return CONTROLLER

