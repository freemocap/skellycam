
import uvicorn
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

def run_api_server():
    app_instance = FastAPIApp()
    uvicorn.run(app_instance.app, host="localhost", port=8000)

if __name__ == '__main__':
    from multiprocessing import Process

    server_process = Process(target=run_api_server)
    server_process.start()