import multiprocessing
import time

from skellycam.__main__ import main


def test_main():
    # just run the main function for a few seconds and check that it doesn't crash
    # it won't exit on its own, so we have to kill it
    main_thread = multiprocessing.Process(target=main)
    main_thread.start()
    time.sleep(3)
    assert main_thread.is_alive()
    main_thread.terminate()
    main_thread.join()
    assert not main_thread.is_alive()
    assert True
