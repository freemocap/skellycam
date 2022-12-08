from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget,QFileDialog,QPushButton,QVBoxLayout

import matplotlib

from GUI_widgets.mediapipe_skeleton_builder import mediapipe_indices, mediapipe_connections, build_skeleton

matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from pathlib import Path
import numpy as np




class SkeletonViewWidget(QWidget):

    session_folder_loaded_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self.folder_open_button = QPushButton('Load a session folder',self)
        self._layout.addWidget(self.folder_open_button)
        self.folder_open_button.clicked.connect(self.open_folder_dialog)

        self.fig,self.ax = self.initialize_skeleton_plot()
        self._layout.addWidget(self.fig)

        self.session_folder_path = None
        

    def open_folder_dialog(self):
        
        self.folder_diag = QFileDialog()
        self.session_folder_path  = QFileDialog.getExistingDirectory(None,"Choose a session")

        if self.session_folder_path:
            self.session_folder_path = Path(self.session_folder_path)

        
        #data_array_folder = 'output_data'
        data_array_folder = 'DataArrays'
        array_name = 'mediaPipeSkel_3d_origin_aligned.npy'
        #array_name = 'mediaPipeSkel_3d.npy'
        #array_name = 'mediaPipeSkel_3d_origin_aligned.npy'
        #array_name = 'mediapipe_3dData_numFrames_numTrackedPoints_spatialXYZ.npy'
        
        skeleton_data_folder_path = self.session_folder_path / data_array_folder/array_name
        self.skel3d_data = np.load(skeleton_data_folder_path)


        self.mediapipe_skeleton = build_skeleton(self.skel3d_data,mediapipe_indices,mediapipe_connections)

        self.num_frames = self.skel3d_data.shape[0]
        # self.reset_slider()
        self.reset_skeleton_3d_plot()
        self.session_folder_loaded_signal.emit()

            
    def initialize_skeleton_plot(self):
        fig = Mpl3DPlotCanvas(self, width=5, height=4, dpi=100)
        ax = fig.figure.axes[0]
        return fig, ax

    def reset_skeleton_3d_plot(self):
        self.ax.cla()
        self.calculate_axes_means(self.skel3d_data)
        self.skel_x,self.skel_y,self.skel_z = self.get_x_y_z_data(0)
        self.plot_skel(0,self.skel_x,self.skel_y,self.skel_z)


    def reset_slider(self):
        self.slider_max = self.num_frames -1
        self.slider.setValue(0)
        self.slider.setMaximum(self.slider_max)

    def calculate_axes_means(self,skeleton_3d_data):
        self.mx_skel = np.nanmean(skeleton_3d_data[:,0:33,0])
        self.my_skel = np.nanmean(skeleton_3d_data[:,0:33,1])
        self.mz_skel = np.nanmean(skeleton_3d_data[:,0:33,2])
        self.skel_3d_range = 900

    def plot_skel(self,frame_number,skel_x,skel_y,skel_z):
        self.ax.scatter(skel_x,skel_y,skel_z)
        self.plot_skeleton_bones(frame_number)
        self.ax.set_xlim([self.mx_skel-self.skel_3d_range, self.mx_skel+self.skel_3d_range])
        self.ax.set_ylim([self.my_skel-self.skel_3d_range, self.my_skel+self.skel_3d_range])
        self.ax.set_zlim([self.mz_skel-self.skel_3d_range, self.mz_skel+self.skel_3d_range])

        self.fig.figure.canvas.draw_idle()

    def plot_skeleton_bones(self,frame_number):
            this_frame_skeleton_data = self.mediapipe_skeleton[frame_number]
            for connection in this_frame_skeleton_data.keys():
                line_start_point = this_frame_skeleton_data[connection][0] 
                line_end_point = this_frame_skeleton_data[connection][1]
                
                bone_x,bone_y,bone_z = [line_start_point[0],line_end_point[0]],[line_start_point[1],line_end_point[1]],[line_start_point[2],line_end_point[2]] 

                self.ax.plot(bone_x,bone_y,bone_z)

    def get_x_y_z_data(self, frame_number:int):
        skel_x = self.skel3d_data[frame_number,:,0]
        skel_y = self.skel3d_data[frame_number,:,1]
        skel_z = self.skel3d_data[frame_number,:,2]

        return skel_x,skel_y,skel_z

    def replot(self, frame_number:int):
        skel_x,skel_y,skel_z = self.get_x_y_z_data(frame_number)
        self.ax.cla()
        self.plot_skel(frame_number,skel_x,skel_y,skel_z)
        #self.label.setText(str(frame_number))


class Mpl3DPlotCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=4, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111,projection = '3d')
        super(Mpl3DPlotCanvas, self).__init__(fig)




