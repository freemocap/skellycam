import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import skellycam
from skellycam.api.server.server_constants import APP_URL
from skellycam.skellycam_app.skellycam_app_controller.skellycam_app_controller import get_skellycam_app_controller
from skellycam.system.default_paths import get_default_skellycam_base_folder_path

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.api("Skellycam API starting...")
    logger.info(f"Skellycam API base folder path: {get_default_skellycam_base_folder_path()}")
    Path(get_default_skellycam_base_folder_path()).mkdir(parents=True, exist_ok=True)

    logger.info("Adding middleware...")

    logger.info(f"Creating `Controller` instance...")
    controller = get_skellycam_app_controller()
    logger.success(f"Skellycam API (version:{skellycam.__version__}) started successfully 💀📸✨")
    logger.api(f"Skellycam API  running on: \n\t\tSwagger API docs - {APP_URL} \n\t\tTest UI: {APP_URL}/skellycam/ui 👈[click to simple test UI in your browser]")

    # # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("Skellycam API ending...")
    controller.shutdown()
    logger.success("Skellycam API shutdown complete - Goodbye!👋")
