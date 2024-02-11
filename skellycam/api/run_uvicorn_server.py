import multiprocessing

import uvicorn

from skellycam.api.fastapi_app import FastApiApp
from skellycam.api.log_api_routes import log_api_routes


def run_uvicorn_server(
    hostname: str, port: int, ready_event: multiprocessing.Event = None
):
    app = FastApiApp(ready_event).app
    log_api_routes(app, hostname, port)
    uvicorn.run(
        app,
        host=hostname,
        port=port,
        log_level="debug"
        # reload=True
    )
