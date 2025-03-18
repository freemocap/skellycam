import logging
import os
from pathlib import Path

from fastapi import APIRouter
from starlette.responses import HTMLResponse

from skellycam.api.server.server_constants import PORT, APP_URL

logger = logging.getLogger(__name__)

ui_router = APIRouter(tags=['App'])


@ui_router.get("/", response_class=HTMLResponse)
def serve_ui():
    logger.info("Serving UI HTML to `/ui`")
    file_path = os.path.join(os.path.dirname(__file__), 'ui.html')
    with open(file_path, 'r', encoding='utf-8') as file:
        ui_html_string = file.read()
    # ui_html_string = ui_html_string.replace("{{HTTP_URL}}", APP_URL)
    # ui_html_string =  ui_html_string.replace("{{WEBSOCKET_URL}}", APP_URL.replace("http", "ws"))
    ui_html_string =  ui_html_string.replace("{{SKELLYCAM_DATA_FOLDER}}", str(Path().home()/"skellycam_data")).replace("\\", "/")
    return HTMLResponse(content=ui_html_string, status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(ui_router, host="localhost", port=PORT)
