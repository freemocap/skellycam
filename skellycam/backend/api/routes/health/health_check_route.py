from fastapi import APIRouter
from pydantic import BaseModel

healthcheck_router = APIRouter()


class HealthCheckResponse(BaseModel):
    message: str = "OK"


@healthcheck_router.get("/health")
def route():
    try:
        return HealthCheckResponse()
    except:
        raise ValueError("Unhealthy")

@healthcheck_router.get("/hello", summary="👋")
async def hello():
    """
    A simple endpoint to greet the user of the SkellyCam API.
    This can be used as a sanity check to ensure the API is responding.
    """
    return {"message": "Hello from the SkellyCam 💀📸✨"}
