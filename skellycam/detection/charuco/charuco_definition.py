import cv2
from dataclasses import dataclass
from typing import Dict

@dataclass
class CharucoBoardDefinition:
    aruco_marker_dict: Dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)
    number_of_squares_width: int = 7
    number_of_squares_height: int = 5
    black_square_side_length: int = 1
    aruco_marker_length_proportional: float = 0.8

    def __post_init__(self):
        self.charuco_board = cv2.aruco.CharucoBoard(
            size=[self.number_of_squares_width, self.number_of_squares_height],
            squareLength=self.black_square_side_length,
            markerLength=self.aruco_marker_length_proportional,
            dictionary=self.aruco_marker_dict,
        )

        self.charuco_detector = cv2.aruco.CharucoDetector(self.charuco_board)

        self.charuco_params = cv2.aruco.DetectorParameters()