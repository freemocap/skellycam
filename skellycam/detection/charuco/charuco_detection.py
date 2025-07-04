import cv2
import numpy as np

from skellycam.detection.charuco.charuco_definition import CharucoBoardDefinition

def draw_charuco_on_image(image: np.ndarray, charuco_board: CharucoBoardDefinition) -> None:
    charuco_corners, charuco_ids, marker_corners, marker_ids = charuco_board.charuco_detector.detectBoard(image)
    if not (marker_ids is None) and len(marker_ids) > 0:
        cv2.aruco.drawDetectedMarkers(image, marker_corners)
    if not (charuco_ids is None) and len(charuco_ids) >= 4:
        cv2.aruco.drawDetectedCornersCharuco(image, charuco_corners, charuco_ids)
