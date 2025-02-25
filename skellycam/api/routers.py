from skellycam.api.http.cameras.close import close_cameras_router
from skellycam.api.http.cameras.connect import connect_cameras_router
from skellycam.api.http.cameras.record import record_cameras_router
from skellycam.api.http.video_playback.open_videos import open_videos_router
from skellycam.api.http.video_playback.play_videos import play_videos_router
from skellycam.api.http.video_playback.pause_videos import pause_videos_router
from skellycam.api.http.video_playback.go_to_frame import seek_videos_router
from skellycam.api.http.video_playback.stop_videos import stop_videos_router
from skellycam.api.http.video_playback.close_videos import close_videos_router

SKELLYCAM_ROUTERS = {
    "/skellycam/cameras": {
        "connect": connect_cameras_router,
        # "detect": detect_cameras_router,
        "record": record_cameras_router,
        "close": close_cameras_router
    },
    "/skellycam/video_playback": {
        "open_videos": open_videos_router,
        "play_videos": play_videos_router,
        "pause_videos": pause_videos_router,
        "stop_videos": stop_videos_router,
        "seek_videos": seek_videos_router,
        "close_videos": close_videos_router
    }

}

