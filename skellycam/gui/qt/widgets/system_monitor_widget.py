import sys
import threading
import multiprocessing
import psutil
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem, QVBoxLayout, QTreeWidget, QWidget, QHBoxLayout


class SystemMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setGeometry(300, 300, 800, 600)
        self.setWindowTitle('System Monitor')

        # Use a QTreeWidget to display the thread and process names
        self.systemTree = QTreeWidget(self)
        self.systemTree.setHeaderLabels(['Type', 'Name', 'ID', 'Status'])
        self.systemTree.setColumnWidth(0, 200)  # Increase width of 'Type' column

        self.threadParentItem = QTreeWidgetItem(self.systemTree, ['Threads'])
        self.processParentItem = QTreeWidgetItem(self.systemTree, ['Processes'])

        # Create another QTreeWidget for the system stats
        self.systemStatsTree = QTreeWidget(self)
        self.systemStatsTree.setHeaderLabels(['Type', 'Value'])
        self.systemStatsTree.setColumnWidth(0, 200)  # Increase width of 'Type' column

        self.systemStatsParentItem = QTreeWidgetItem(self.systemStatsTree, ['System Stats'])

        layout = QHBoxLayout(self)
        layout.addWidget(self.systemTree)
        layout.addWidget(self.systemStatsTree)

        self.timer = QTimer()
        self.timer.setInterval(1000)  # 1000 ms = 1 second
        self.timer.timeout.connect(self.updateSystemTree)
        self.timer.start()

    def updateSystemTree(self):
        self.threadParentItem.takeChildren()
        self.processParentItem.takeChildren()
        self.systemStatsParentItem.takeChildren()

        # Iterate over all the running threads and add their names and IDs to the tree
        for thread in threading.enumerate():
            thread_status = 'Active'  # By default, if the thread is in enumerate, it's active
            QTreeWidgetItem(self.threadParentItem, ['Thread', thread.name, str(thread.ident), thread_status])

        # Use psutil to iterate over all child processes of the current process
        for proc in psutil.Process().children(recursive=True):
            QTreeWidgetItem(self.processParentItem, ['Process', proc.name(), str(proc.pid), proc.status()])

        # Display system stats
        cpu_percent = psutil.cpu_percent()
        available_memory = psutil.virtual_memory().available / (1024.0 ** 3)
        total_memory = psutil.virtual_memory().total / (1024.0 ** 3)

        QTreeWidgetItem(self.systemStatsParentItem, ['CPU Load', f'{cpu_percent:.3f}%'])
        QTreeWidgetItem(self.systemStatsParentItem, ['Available Memory', f'{available_memory:.3f} GB'])
        QTreeWidgetItem(self.systemStatsParentItem, ['Total Memory', f'{total_memory:.3f} GB'])

        self.systemTree.expandAll()

