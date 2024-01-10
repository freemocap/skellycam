from fastapi import FastAPI

from skellycam.api.routers import camera_router


class FastAPIApp:
    def __init__(self):
        self.app = FastAPI()
        self._register_routes()
    def _register_routes(self):
        self.app.include_router(camera_router.router)
        self.app.get("/")(self.read_root)

    async def read_root(self):
        return {"message": "Hello from SkellyCam 💀📸✨"}
