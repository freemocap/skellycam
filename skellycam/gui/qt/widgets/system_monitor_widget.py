import sys
import threading
import multiprocessing
import psutil
from typing import Callable

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem, QVBoxLayout, QTreeWidget, QWidget

class SystemMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setGeometry(300, 300, 400, 600)
        self.setWindowTitle('System Monitor')

        # Use a QTreeWidget to display the thread and process names
        self.systemTree = QTreeWidget(self)
        self.systemTree.setHeaderLabels(['Type', 'Name', 'PID', 'Status'])

        self.threadParentItem = QTreeWidgetItem(self.systemTree, ['Threads'])
        self.processParentItem = QTreeWidgetItem(self.systemTree, ['Processes'])

        layout = QVBoxLayout(self)
        layout.addWidget(self.systemTree)

        self.timer = QTimer()
        self.timer.setInterval(1000)  # 1000 ms = 1 second
        self.timer.timeout.connect(self.updateSystemTree)
        self.timer.start()

    def updateSystemTree(self):
        self.threadParentItem.takeChildren()
        self.processParentItem.takeChildren()

        # Iterate over all the running threads and add their names to the tree
        for thread in threading.enumerate():
            QTreeWidgetItem(self.threadParentItem, ['Thread', thread.name, '-'])

        # Use psutil to iterate over all child processes of the current process
        for proc in psutil.Process().children(recursive=True):
            QTreeWidgetItem(self.processParentItem, ['Process', proc.name(), str(proc.pid), proc.status()])

        self.systemTree.expandAll()


def main():

    app = QApplication(sys.argv)

    monitor = SystemMonitor()
    monitor.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
