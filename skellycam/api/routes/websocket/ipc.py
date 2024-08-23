import multiprocessing

# A pipe to communicate between the frontend websocket relay and the frame wrangler (SEND BYTES ONLY)
FRONTEND_WS_RELAY_PIPE, FRAME_WRANGLER_PIPE = multiprocessing.Pipe()


def get_frontend_ws_relay_frame_pipe():
    return FRONTEND_WS_RELAY_PIPE


def get_frame_wrangler_pipe():
    return FRAME_WRANGLER_PIPE


# A queue to communicated between the main process and the sub-processes
IPC_QUEUE = multiprocessing.Queue()


def get_ipc_queue():
    return IPC_QUEUE
