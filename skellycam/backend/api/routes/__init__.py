from skellycam.backend.api.routes.camera.camera_route import camera_router
from skellycam.backend.api.routes.camera.camera_websocket import cam_ws_router
from skellycam.backend.api.routes.health.health_check_route import healthcheck_router
from skellycam.backend.api.routes.startup.startup import startup_router

enabled_routers = [healthcheck_router, camera_router, cam_ws_router, startup_router]