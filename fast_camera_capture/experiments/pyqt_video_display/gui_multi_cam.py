from PyQt6.QtWidgets import QMainWindow, QWidget, QApplication, QHBoxLayout,QVBoxLayout, QPushButton, QFileDialog
from GUI_widgets.skeleton_view_widget import SkeletonViewWidget
from GUI_widgets.slider_widget import FrameCountSlider
from GUI_widgets.multi_camera_capture_widget import MultiVideoDisplay

from pathlib import Path
from glob import glob



class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("My App")


        layout = QHBoxLayout()
        widget = QWidget()

        slider_and_skeleton_layout = QVBoxLayout()

        self.frame_count_slider = FrameCountSlider()
        slider_and_skeleton_layout.addWidget(self.frame_count_slider)

        self.skeleton_view_widget = SkeletonViewWidget()
        self.skeleton_view_widget.setFixedSize(self.skeleton_view_widget.size())
        slider_and_skeleton_layout.addWidget(self.skeleton_view_widget)
        layout.addLayout(slider_and_skeleton_layout)

        self.multi_video_display = MultiVideoDisplay()
        # self.multi_video_display.setFixedSize(self.skeleton_view_widget.size()*1.5)
        layout.addWidget(self.multi_video_display)
            
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.connect_signals_to_slots()


        f = 2

    def connect_signals_to_slots(self):

        self.skeleton_view_widget.session_folder_loaded_signal.connect(lambda: self.frame_count_slider.set_slider_range(self.skeleton_view_widget.num_frames))
        self.skeleton_view_widget.session_folder_loaded_signal.connect(lambda: self.multi_video_display.video_folder_load_button.setEnabled(True))
        self.skeleton_view_widget.session_folder_loaded_signal.connect(lambda: self.multi_video_display.set_session_folder_path(self.skeleton_view_widget.session_folder_path))

        self.frame_count_slider.slider.valueChanged.connect(lambda: self.skeleton_view_widget.replot(self.frame_count_slider.slider.value()))
        self.frame_count_slider.slider.valueChanged.connect(lambda: self.multi_video_display.update_display(self.frame_count_slider.slider.value()) if (self.multi_video_display.are_videos_loaded) else None)



        
if __name__ == "__main__":

    app = QApplication([])
    win = MainWindow()
    win.show()
    app.exec()
