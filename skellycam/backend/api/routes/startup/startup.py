from pathlib import Path

from fastapi import APIRouter

from skellycam.system.default_paths import get_default_skellycam_base_folder_path

startup_router = APIRouter()


@startup_router.on_event("startup")
async def handle_startup():
    Path(get_default_skellycam_base_folder_path()).mkdir(parents=True, exist_ok=True)
