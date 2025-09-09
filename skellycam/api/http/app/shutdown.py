"""
Clean shutdown endpoint with proper async handling.
"""
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

shutdown_router = APIRouter(tags=["System"])


@shutdown_router.post(
    "/shutdown",
    summary="Gracefully shutdown the server",
    response_model=dict[str, str]
)
async def shutdown_server(
        request: Request,
        background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Initiate graceful server shutdown.

    This endpoint triggers a graceful shutdown of the entire SkellyCam system,
    including all camera groups and the server itself.

    Returns:
        JSON response confirming shutdown initiation
    """
    logger.api("Shutdown requested via API")

    # Get app instance from request
    app = request.app

    # Schedule shutdown in background to allow response to be sent
    background_tasks.add_task(_perform_shutdown, app)

    return JSONResponse(
        content={
            "status": "shutdown_initiated",
            "message": "Server is shutting down gracefully. Goodbye! 👋"
        },
        status_code=200
    )


async def _perform_shutdown(app) -> None:
    """
    Perform the actual shutdown sequence.

    Args:
        app: FastAPI application instance
    """
    # Small delay to ensure response is sent
    await asyncio.sleep(0.5)

    try:
        # Shutdown SkellyCam application
        if hasattr(app.state, 'skellycam_app'):
            logger.info("Shutting down SkellyCam application...")
            app.state.skellycam_app.shutdown()

        # Set global kill flag
        if hasattr(app.state, 'global_kill_flag'):
            logger.info("Setting global kill flag...")
            app.state.global_kill_flag.value = True

        # Trigger server shutdown
        # This works because we store the server reference in app state
        if hasattr(app.state, 'server'):
            logger.info("Triggering server shutdown...")
            app.state.server.should_exit = True

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        # Force kill flag even on error
        if hasattr(app.state, 'global_kill_flag'):
            app.state.global_kill_flag.value = True

    logger.info("Shutdown sequence complete")


@shutdown_router.get(
    "/health/shutdown-status",
    summary="Check if shutdown is in progress",
    response_model=dict[str, object]
)
async def shutdown_status(request: Request) -> dict[str, object]:
    """
    Check if the system is shutting down.

    Returns:
        Status of the shutdown flag
    """
    app = request.app
    is_shutting_down = False

    if hasattr(app.state, 'global_kill_flag'):
        is_shutting_down = bool(app.state.global_kill_flag.value)

    return {
        "is_shutting_down": is_shutting_down,
        "status": "shutting_down" if is_shutting_down else "running"
    }