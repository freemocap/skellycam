import cv2
from PyQt6 import QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QFileDialog,QGridLayout

from pathlib import Path

class VideoProcessingWorker():
    #this is a worker that handles all the video processing stuff - loading the videos as well as grabbing, converting, and displaying frames
    def __init__(self, video_path: Path):
        self.video_path = video_path
        self.video_capture_object = self.load_video_from_path()

    def load_video_from_path(self):
        #create an opencv object for the video 
        video_capture_object = cv2.VideoCapture(str(self.video_path))
        return video_capture_object

    def run_worker(self,frame_number:int):
        #whenever a frame number is given, set the video to the frame, read it out, and convert it to a pixmap
        self.set_video_to_frame(frame_number)
        frame = self.read_frame_from_video()
        self.pixmap = self.convert_frame_to_pixmap(frame)
        
    def set_video_to_frame(self,frame_number:int):
        self.video_capture_object.set(cv2.CAP_PROP_POS_FRAMES,frame_number)
    
    def read_frame_from_video(self):
        ret, frame = self.video_capture_object.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame
    
    def convert_frame_to_pixmap(self,frame):
        img = QtGui.QImage(frame, frame.shape[1], frame.shape[0], QtGui.QImage.Format.Format_RGB888)
        QtGui.QPixmap()
        pix = QtGui.QPixmap.fromImage(img)
        resized_pixmap = pix.scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio)
        return resized_pixmap
        
    def display_frame(self, video_frame_widget, pixmap):
        #display the frame in the video label widget
        self.video_frame_widget = video_frame_widget
        self.video_frame_widget.setPixmap(pixmap)


class MultiVideoDisplay(QWidget):
    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.video_folder_load_button = QPushButton('Load a folder of videos',self)
        self.video_folder_load_button.setEnabled(False)
        self._layout.addWidget(self.video_folder_load_button)
        self.video_folder_load_button.clicked.connect(self.load_video_folder)

        self.video_display_layout = QGridLayout()
        self._layout.addLayout(self.video_display_layout)

        self.are_videos_loaded = False #bool to let you move the slider in the main GUI without having loaded videos

    def set_session_folder_path(self,session_folder_path:Path):
        self.session_folder_path = session_folder_path

    def load_video_folder(self):
        #get a path to the video folder, generate a list of the video paths and the number of videos and create the video display widget based on that 
        self.folder_diag = QFileDialog()
        self.video_folder_path  = QFileDialog.getExistingDirectory(None,"Choose a folder of videos", directory=str(self.session_folder_path))
        self.list_of_video_paths, self.number_of_videos = self.create_list_of_video_paths(self.video_folder_path)
        self.generate_video_display(self.list_of_video_paths,self.number_of_videos)

        self.are_videos_loaded = True 
    
    def create_list_of_video_paths(self,path_to_video_folder:Path):
        #search the folder for 'mp4' files and create a list of them 
        list_of_video_paths = list(Path(path_to_video_folder).glob('*.mp4'))
        number_of_videos = len(list_of_video_paths)
        return list_of_video_paths, number_of_videos

    def generate_video_display(self,list_of_video_paths:list,number_of_videos:int):
        self.video_worker_dictionary = self.generate_video_workers(list_of_video_paths)
        self.label_widget_dictionary = self.generate_label_widgets_for_videos(number_of_videos)
        self.add_widgets_to_layout()

        return self.video_worker_dictionary, self.label_widget_dictionary

    def generate_video_workers(self, list_of_video_paths:list):
        #for every video, create a worker that can handle the video processing and add it to the dictionary 
        self.video_worker_dictionary = {}

        for count, video_path in enumerate(list_of_video_paths):
            self.video_worker_dictionary[count] = VideoProcessingWorker(video_path)

        return self.video_worker_dictionary
        f = 2 

    def generate_label_widgets_for_videos(self,number_of_videos:int):
        label_widget_dictionary = {}
        for x in range(number_of_videos):
            label_widget_dictionary[x] = QLabel('Video {}'.format(str(x)))

        self.number_of_videos = number_of_videos
        
        return label_widget_dictionary

    def add_widgets_to_layout(self):
        column_count = 0
        row_count = 0
        for widget in self.label_widget_dictionary:
            self.video_display_layout.addWidget(self.label_widget_dictionary[widget],row_count,column_count)

            # This section is for formatting the videos in the grid nicely - it fills out two columns and then moves on to the next row
            column_count +=1
            if column_count%2 == 0:
                column_count = 0
                row_count += 1
    
    def update_display(self, frame_number:int):
        for x in range(self.number_of_videos):
            this_vid_worker = self.video_worker_dictionary[x]
            this_vid_worker.run_worker(frame_number)
            this_vid_worker.display_frame(self.label_widget_dictionary[x],this_vid_worker.pixmap) 








