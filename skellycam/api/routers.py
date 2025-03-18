from skellycam.api.http.cameras.cameras_connect_router import connect_cameras_router

SKELLYCAM_ROUTERS = {
    "/skellycam": {
        "connect": connect_cameras_router,
        # "configs": camera_configs_router,
        # "record": record_cameras_router,
        # "close": close_cameras_router
    },

}

