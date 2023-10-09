import multiprocessing

from PySide6.QtGui import QShortcut, QKeySequence

from skellycam import logger


class KeyboardShortcuts:
    def __init__(self, exit_event: multiprocessing.Event, reboot_event: multiprocessing.Event):
        self.exit_event = exit_event
        self.reboot_event = reboot_event

    def connect_shortcuts(self, window):
        logger.debug(f"Connecting keyboard shortcuts to window: {window}")
        self.connect_quit(window)
        self.connect_reboot(window)

    def connect_quit(self, window):
        QShortcut(QKeySequence('Ctrl+Q'), window, activated=self._handle_quit)

    def connect_reboot(self, window):
        QShortcut(QKeySequence('Ctrl+R'), window, activated=self._handle_reboot)

    def _handle_quit(self):
        logger.info(f"Heard `Ctrl+Q`, exiting...")
        self.exit_event.set()

    def _handle_reboot(self):
        logger.info(f"Heard `Ctrl+R`, rebooting...")
        self.reboot_event.set()
