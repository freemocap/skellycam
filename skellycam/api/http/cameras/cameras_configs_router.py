import json
import logging

from fastapi import APIRouter, Body

from skellycam import CameraId
from skellycam.core.camera_group.camera.config.camera_config import CameraConfigs, default_camera_configs_factory
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller
from pydantic import model_validator, BaseModel

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



@camera_configs_router.get(
    "/configs/exposure/recommend",
    summary="Estimate and set recommended exposure settings for all available cameras",
)
def cameras_configs_exposure_recommend_get_endpoint():
    logger.api("Received `skellycam/configs/exposure/recommend` GET request...")
    try:
        get_skellycam_app_controller().set_recommended_exposure()
        logger.api("`skellycam/configs/exposure/recommend` GET request handled successfully.")
    except Exception as e:
        logger.error(f"Failed to set recommended exposure: {type(e).__name__} - {e}")
        logger.exception(e)
