import multiprocessing

from PySide6.QtGui import QShortcut, QKeySequence

from skellycam.system.environment.get_logger import logger


class KeyboardShortcuts:
    def __init__(self, exit_event: multiprocessing.Event, reboot_event: multiprocessing.Event):
        self.exit_event = exit_event
        self.reboot_event = reboot_event

    def connect_shortcuts(self, window):
        logger.debug(f"Connecting keyboard shortcuts to window: {window}")
        self.connect_quit(window)
        self.connect_reboot(window)

    def connect_quit(self, window):
        QShortcut(QKeySequence('Ctrl+Q'), window, activated=self.quit)

    def connect_reboot(self, window):
        # QShortcut(QKeySequence('Ctrl+R'), window, activated=self.reboot)
        pass

    def quit(self):
        logger.info(f"SETTING EXIT EVENT")
        self.exit_event.set()

    def reboot(self):
        logger.info(f"SETTING REBOOT EVENT")
        self.reboot_event.set()
