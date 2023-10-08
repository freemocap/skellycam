import logging
import multiprocessing.connection
import sys

from skellycam.frontend.qt.skelly_cam_main_window import SkellyCamMainWindow
from skellycam.frontend.qt.utilities.get_qt_app import get_qt_app

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QTimer


def frontend_main(frontend_to_backend: multiprocessing.connection.Connection,
                  backend_to_frontend: multiprocessing.connection.Connection):
    app = get_qt_app(sys.argv)

    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: update)  # Let the interpreter run each 500 ms.

    def update():
        if backend_to_frontend.poll():
            msg = backend_to_frontend.recv()
            print(f"frontend_main received message: {msg}")
            if msg == "quit":
                app.quit()
            else:
                raise ValueError(f"frontend_main received unexpected message: {msg}")

    main_window = SkellyCamMainWindow()
    main_window.show()
    error_code = app.exec()

    logger.info(f"Exiting with code: {error_code}")
    print("Thank you for using Skelly Cam \U0001F480 \U0001F4F8")
    sys.exit()


if __name__ == "__main__":
    frontend_main()
