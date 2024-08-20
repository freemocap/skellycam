import multiprocessing

FRONTEND_QUEUE: multiprocessing.Queue = multiprocessing.Queue()


def get_frontend_queue():
    return FRONTEND_QUEUE
