import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import skellycam
from skellycam.api.server.server_constants import APP_URL
from skellycam.api.server.server_kill_event import get_kill_event
from skellycam.core.controller import create_controller
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
    controller = create_controller(kill_event=get_kill_event())
    logger.success(f"Skellycam API (version:{skellycam.__version__}) started successfully 💀📸✨")
    logger.api(f"Skellycam API  running on: {APP_URL}  👈[click to open backend UI in your browser]\n")
    logger.api(f"Skellycam API  test ui: {APP_URL}/ui  👈[click to open backend UI in your browser]\n")

    # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("Skellycam API ending...")
    await controller.close()
    logger.success("Skellycam API shutdown complete - Goodbye!👋")
