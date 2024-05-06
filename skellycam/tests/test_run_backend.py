import multiprocessing

from skellycam.run_backend import run_backend


def test_run_backend_starts_process():
    ready_event = multiprocessing.Event()
    shutdown_event = multiprocessing.Event()
    backend_process, hostname, port = run_backend(ready_event, shutdown_event, 5)

    assert backend_process.is_alive() == True
    # Add more assertions as needed to check for correct hostname, port, etc.
