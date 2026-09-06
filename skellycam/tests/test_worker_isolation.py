"""Worker failures stop their owner without stopping unrelated workers."""

import multiprocessing
from multiprocessing.sharedctypes import Synchronized
import os
import time

import pytest

from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry


def wait_for_stop(*, stop: Synchronized) -> None:
    while not stop.value:
        time.sleep(0.01)


def crash_worker() -> None:
    raise RuntimeError("Deliberate worker failure")


def exit_abruptly() -> None:
    os._exit(17)


@pytest.mark.parametrize("mode,abrupt", [(WorkerMode.PROCESS, False), (WorkerMode.THREAD, False), (WorkerMode.PROCESS, True)])
def test_owner_failure_isolation(mode: WorkerMode, abrupt: bool) -> None:
    application = multiprocessing.Value("b", False)
    owner = multiprocessing.Value("b", False)
    independent = multiprocessing.Value("b", False)
    registry = WorkerRegistry(global_kill_flag=application, worker_mode=mode)
    sibling = registry.create_worker(worker_mode=registry.worker_mode, shutdown_flag=owner, target=wait_for_stop, name="sibling", kwargs={"stop": owner})
    unrelated = registry.create_worker(worker_mode=registry.worker_mode, shutdown_flag=independent, target=wait_for_stop, name="unrelated", kwargs={"stop": independent})
    failing = registry.create_worker(worker_mode=registry.worker_mode, shutdown_flag=owner, target=exit_abruptly if abrupt else crash_worker, name="failing")
    registry.start_heartbeat()
    try:
        sibling.start()
        unrelated.start()
        failing.start()
        deadline = time.monotonic() + 20
        while (failing.is_alive() or sibling.is_alive()) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not failing.is_alive()
        assert not sibling.is_alive()
        assert failing.failure_exitcode is not None
        assert owner.value
        assert not application.value
        assert not independent.value
        assert unrelated.is_alive()
    finally:
        for worker in registry.workers:
            worker.mark_stopping()
        owner.value = True
        independent.value = True
        for worker in registry.workers:
            if worker.pid is not None:
                worker.terminate_gracefully()
        registry.shutdown_all()
