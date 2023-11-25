import multiprocessing

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

DUMMY_APP_STATE = {"app": "state"}


# Backend process
def backend_process(backend_conn):
    while True:
        message = backend_conn.recv()
        print("Backend received: ", message)
        backend_conn.send({"success": True})


# Frontend process
def frontend_process(frontend_conn):
    app = QApplication([])
    timer = QTimer()
    timer.start(500)  # 500ms

    def send_app_state():
        frontend_conn.send(DUMMY_APP_STATE)
        response = frontend_conn.recv()
        print("Frontend received: ", response)

    timer.timeout.connect(send_app_state)
    app.exec()


if __name__ == "__main__":
    frontend_conn, backend_conn = multiprocessing.Pipe()

    backend = multiprocessing.Process(target=backend_process, args=(backend_conn,))
    frontend = multiprocessing.Process(target=frontend_process, args=(frontend_conn,))

    backend.start()
    frontend.start()

    backend.join()
    frontend.join()