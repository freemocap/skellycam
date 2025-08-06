import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import skellycam
  from skellycam.api.grpc.grpc_server import start_grpc_server
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

    # Start the gRPC server
    logger.debug("Starting gRPC server...")
    grpc_task: asyncio.Task = asyncio.create_task(start_grpc_server())

    logger.success(f"Skellycam API (version:{skellycam.__version__}) started successfully 💀📸✨")
    logger.api(f"Skellycam API  running on: \n\t\tSwagger API docs - {APP_URL}")# \n\t\tTest UI: {APP_URL}/skellycam/ui 👈[click to simple test UI in your browser]")

    # # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("Skellycam API ending...")
    get_skellycam_app().shutdown_skellycam()
    grpc_task.cancel()
    try:
        await grpc_task
    except asyncio.CancelledError:
        logger.info("gRPC server task cancelled successfully.")
    except Exception as e:
        logger.exception(f"Error while shutting down gRPC server: {e}")
    logger.success("Skellycam API shutdown complete - Goodbye!👋")
