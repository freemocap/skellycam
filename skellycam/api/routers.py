from skellycam.api.http.cameras.cameras_connect_router import connect_cameras_router
from skellycam.api.http.cameras.cameras_record_router import record_cameras_router
from skellycam.api.http.videos.videos_router import load_videos_router

SKELLYCAM_ROUTERS = {
    "/skellycam": {
        "cameras": {
            "connect": connect_cameras_router,
            "record": record_cameras_router
        },
        "videos" : {
            "load": load_videos_router,
        }
    },

}

