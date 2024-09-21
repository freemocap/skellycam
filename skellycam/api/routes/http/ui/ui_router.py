import logging
import os

from fastapi import APIRouter
from starlette.responses import HTMLResponse

from skellycam.api.routes.http.ui.ui_html import UI_HTML_STRING

logger = logging.getLogger(__name__)

ui_router = APIRouter()



@ui_router.get("/", response_class=HTMLResponse)
async def serve_ui():
    logger.info("Serving UI HTML to `/ui`")
    file_path = os.path.join(os.path.dirname(__file__), 'ui.html')
    with open(file_path, 'r') as file:
        ui_html_string = file.read()
    return HTMLResponse(content=ui_html_string, status_code=200)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(ui_router, host="localhost", port=8000)
