import pytest
from pytest_mock import MockerFixture
import multiprocessing

from skellycam.backend.api_server.run_uvicorn_server import run_uvicorn_server


def test_run_uvicorn_server(mocker: MockerFixture) -> None:
    # Mock the uvicorn.run function to prevent the actual server from running
    mocker.patch("uvicorn.run", return_value=None)

    ready_event: multiprocessing.Event = multiprocessing.Event()
    shutdown_event: multiprocessing.Event = multiprocessing.Event()

    # You might need to run this in a separate thread or process depending on your setup
    # If so, make sure to join the thread or process at the end of the test
    run_uvicorn_server("localhost", 8000, ready_event, shutdown_event, 5)

    # Check if the ready_event was set, indicating the server is "ready".
    assert ready_event.is_set() == True

    # Trigger the shutdown event to simulate a shutdown.
    shutdown_event.set()

    # Add more assertions or cleanup if necessary
