import json
import logging

from fastapi import APIRouter, Body

from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, default_camera_configs_factory
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller
from skellycam.tests.conftest import camera_configs_fixture

logger = logging.getLogger(__name__)

camera_configs_router = APIRouter()


@camera_configs_router.post(
    "/configs",

    summary="Update camera configurations for camera ids specified by the keys of the request body",
)
def cameras_configs_post_endpoint(
        request: CameraConfigs = Body(..., examples=[default_camera_configs_factory()])
):
    logger.api(f"Received `skellycam/configs/` POST request: \n {json.dumps(request, indent=2)}...")
    try:
        get_skellycam_app_controller().update_camera_configs(update_configs=request)
        logger.api("`skellycam/connect/` POST request handled successfully.")
    except Exception as e:
        logger.error(f"Error when processing `/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)


