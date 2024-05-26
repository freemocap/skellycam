from pytest_mock import MockerFixture

from skellycam.api.run_server import run_uvicorn_server


def test_run_uvicorn_server(mocker: MockerFixture) -> None:
    mocker.patch("uvicorn.run", return_value=None)
    run_uvicorn_server(hostname="localhost", port=8000)
    assert True
