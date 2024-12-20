from skellycam.api.http.cameras.close import close_cameras_router
from skellycam.api.http.cameras.connect import connect_cameras_router
from skellycam.api.http.cameras.record import record_cameras_router

SKELLYCAM_ROUTERS = {
    "/skellycam/cameras": {
        "connect": connect_cameras_router,
        # "detect": detect_cameras_router,
        "record": record_cameras_router,
        "close": close_cameras_router
    },

}

