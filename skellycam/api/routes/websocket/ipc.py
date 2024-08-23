import multiprocessing

IPC_QUEUE = multiprocessing.Queue()
get_ipc_queue = lambda: IPC_QUEUE

FRONTEND_WS_RELAY_PIPE, FRAME_WRANGLER_PIPE = multiprocessing.Pipe()
get_frontend_ws_relay_pipe = lambda: FRONTEND_WS_RELAY_PIPE
get_frame_wrangler_pipe = lambda: FRAME_WRANGLER_PIPE
