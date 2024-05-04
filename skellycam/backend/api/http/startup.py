import logging
from pathlib import Path

from fastapi import APIRouter

from skellycam.system.default_paths import get_default_skellycam_base_folder_path

logger = logging.getLogger(__name__)

startup_router = APIRouter()


@startup_router.on_event("startup")
async def handle_startup():
    logger.api("Skellycam API start-up event triggered.")
    Path(get_default_skellycam_base_folder_path()).mkdir(parents=True, exist_ok=True)
    logger.success("Skellycam API started successfully 💀📸✨")
