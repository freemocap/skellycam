from dataclasses import dataclass

import cv2
import numpy as np

from skellycam.core.frames.timestamps.framerate_tracker import FrameRateTracker


@dataclass
class ImageAnnotator:
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    color_top = (255, 0, 255)  # FFOOFF!
    thickness_top = 3
    color_bottom = (125, 0, 255) # 000OFF!
    thickness_bottom = 4
    position_x = 10 # top-left corner (x: left, +X is rightward)
    position_y = 50 # top-left corner (y: top, +Y is downward)
    vertical_offset = 50

    def annotate_image(self,
                       image: np.ndarray,
                       multi_frame_number: int,
                       framerate_tracker: FrameRateTracker,
                       frame_number: int,
                       camera_id: int) -> np.ndarray:
        annotated_image = image.copy()
        image_height, image_width, _ = image.shape
        # cv2.rectangle(annotated_image, (0, 0), (300, 80), (255, 255, 255, .2), -1)
        for _ in range(2):
            if _ == 0:
                color = self.color_top
                thickness = self.thickness_top
            else:
                color = self.color_bottom
                thickness = self.thickness_bottom
            cv2.putText(annotated_image,
                        f" CameraId: {camera_id}, Frame#{frame_number})",
                        (self.position_x, self.position_y), self.font, self.font_scale, color, thickness)

            cv2.putText(annotated_image, f"MultiFrame# {multi_frame_number}", (self.position_x, self.position_y + self.vertical_offset), self.font, self.font_scale, color, thickness)
            for i, string in enumerate(framerate_tracker.to_string_list()):
                cv2.putText(annotated_image, string, (self.position_x, self.position_y + (i + 2) * self.vertical_offset), self.font, self.font_scale, color, thickness)


            frame_durations = framerate_tracker.frame_durations_ns

            # Calculate the start index based on the length of frame_durations and image width
            step_size = 5
            start_index = max(0, len(frame_durations) - image_width)
            # make it a multiple of step_size
            start_index = start_index - (start_index % step_size)
            # Plot the time series as circles
            for px in range(0, image_width, step_size):
                data_index = start_index + px
                if data_index < len(frame_durations):
                    duration_ms = frame_durations[data_index] / 1e6
                    y_position = int(image_height - duration_ms)
                    cv2.circle(annotated_image, (px, y_position), 3, (255, 0, 255), -1)
            cv2.line(annotated_image, (0, image_height - 33), (image_width, image_height - 33), (255, 255, 255), 1)
            cv2.putText(annotated_image, f"(33ms)", (10, image_height - 36), self.font, self.font_scale/2, (255, 125, 0), 2)
        return annotated_image
