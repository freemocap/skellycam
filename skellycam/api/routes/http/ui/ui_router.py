import logging

from fastapi import APIRouter
from starlette.responses import HTMLResponse

from skellycam.api.routes.http.ui.ui_html import UI_HTML_STRING

logger = logging.getLogger(__name__)

ui_router = APIRouter()




@ui_router.get("/", response_class=HTMLResponse)
async def serve_ui():
    logger.api("Serving UI HTML to `/ui``")
    return HTMLResponse(content=UI_HTML_STRING, status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(ui_router, host="localhost", port=8000)
