import multiprocessing

from pytest_mock import MockerFixture

from skellycam.api.run_server import run_uvicorn_server


def test_run_uvicorn_server(mocker: MockerFixture) -> None:
    # Mock the uvicorn.run function to prevent the actual server from running
    mocker.patch("uvicorn.run", return_value=None)

    # You might need to run this in a separate thread or process depending on your setup
    # If so, make sure to join the thread or process at the end of the test
    run_uvicorn_server(hostname="localhost", port=8000)
    assert True

