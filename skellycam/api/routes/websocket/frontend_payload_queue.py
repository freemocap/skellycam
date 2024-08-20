import multiprocessing

FRONTEND_PAYLOAD_QUEUE: multiprocessing.Queue = multiprocessing.Queue()


def get_frontend_payload_queue():
    return FRONTEND_PAYLOAD_QUEUE
