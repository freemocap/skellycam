import logging

from fastapi import APIRouter

from skellycam.api.app.app_state import get_app_state

HELLO_FROM_SKELLYCAM_BACKEND_MESSAGE = {"message": "Hello from the SkellyCam Backend 💀📸✨"}

logger = logging.getLogger(__name__)
health_router = APIRouter()


@health_router.get("/healthcheck", summary="Hello👋")
async def healthcheck_endpoint():
    """
    A simple endpoint to greet the user of the SkellyCam API.

    This can be used as a sanity check to ensure the API is responding.
    """
    get_app_state().log_api_call("app/healthcheck")

    logger.api("Hello requested! Deploying Hello!")
    return HELLO_FROM_SKELLYCAM_BACKEND_MESSAGE
