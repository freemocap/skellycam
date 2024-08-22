import logging
from pathlib import Path

from fastapi import APIRouter
from starlette.responses import HTMLResponse

from skellycam.api.app.app_state import get_app_state

logger = logging.getLogger(__name__)

ui_router = APIRouter()


def load_html_file(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

@ui_router.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_file = str(Path(__file__).parent / "ui.html")
    logger.api("Serving UI HTML to `/ui` from: `{html_file}`")
    get_app_state().log_api_call("ui/")
    return HTMLResponse(content=load_html_file(html_file), status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(ui_router, host="localhost", port=8000)
