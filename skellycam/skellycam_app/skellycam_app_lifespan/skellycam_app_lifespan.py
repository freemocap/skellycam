import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import rerun as rr
import skellycam
from skellycam.api.server.server_constants import APP_URL
from skellycam.skellycam_app.skellycam_app import get_skellycam_app
from skellycam.system.default_paths import get_default_skellycam_base_folder_path

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.api("Skellycam API starting...")
    logger.info(f"Skellycam API base folder path: {get_default_skellycam_base_folder_path()}")
    Path(get_default_skellycam_base_folder_path()).mkdir(parents=True, exist_ok=True)

    rr.init("rerun_example_multiprocessing")
    rr.spawn(connect=False, memory_limit="10GB")  # this is the Viewer that each child process will connect to

    logger.info("Adding middleware...")
    skellycam_app = get_skellycam_app()
    logger.success(f"Skellycam API (version:{skellycam.__version__}) started successfully 💀📸✨")
    logger.api(f"Skellycam API  running on: \n\t\tSwagger API docs - {APP_URL} \n\t\tTest UI: {APP_URL}/skellycam/ui 👈[click to simple test UI in your browser]")

    # # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("Skellycam API ending...")
    skellycam_app.shutdown_skellycam()
    logger.success("Skellycam API shutdown complete - Goodbye!👋")
