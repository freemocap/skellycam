import logging

from fastapi.routing import APIRoute
from starlette.routing import WebSocketRoute

logger = logging.getLogger(__name__)


def log_api_routes(app, hostname, port):
    debug_string = f"Starting Uvicorn server on `{hostname}:{port}` serving routes:\n"
    api_routes = ""
    websocket_routes = ""
    for route in app.routes:
        if isinstance(route, APIRoute):
            api_routes += f"\tRoute: `{route.name}`, path: `{route.path}`, methods: {route.methods}\n"

        elif isinstance(route, WebSocketRoute):
            websocket_routes += f"\tRoute: `{route.name}`, path: `{route.path}`"
    debug_string += f"HTTP routes: \n{api_routes}\nWebsockets: \n{websocket_routes}\n"
    logger.info(debug_string)
