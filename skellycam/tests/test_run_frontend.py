import multiprocessing
from multiprocessing import Process

from pytest_mock import MockerFixture

from skellycam.frontend import run_frontend


def test_run_frontend_starts_process(mocker: MockerFixture) -> None:
    # Mock the run_qt_application function to prevent the actual GUI from running
    mocker.patch(
        "skellycam.frontend.qt_application.run_qt_application", return_value=None
    )

    reboot_event: multiprocessing.Event = multiprocessing.Event()
    shutdown_event: multiprocessing.Event = multiprocessing.Event()

    frontend_process: Process = run_frontend(
        "localhost", 8000, 5, reboot_event, shutdown_event
    )

    assert frontend_process.is_alive() == True
    # Add more assertions if necessary

    frontend_process.terminate()  # Make sure to terminate the process after the test
