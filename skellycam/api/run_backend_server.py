import socket

import uvicorn

from skellycam.api.fastapi_app import FastAPIApp


def find_available_port(start_port):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except socket.error as e:
                print(f"Port {port} is in use.")
                port += 1
                if port > 65535:  # No more ports available
                    raise e
def run_backend_api_server():
    app_instance = FastAPIApp()
    port = find_available_port(8000)

    uvicorn.run(app_instance.app,
                host="localhost",
                port=port,
                # reload=True # TODO - Figure out how to enable `reload` for the FastAPI app
                )

if __name__ == '__main__':
    from multiprocessing import Process

    server_process = Process(target=run_backend_api_server)
    server_process.start()