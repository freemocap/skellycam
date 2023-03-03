import cv2
import numpy as np

from skellycam.detection.models.frame_payload import FramePayload


class ImageAnnotator:
    def annotate(self, image: np.ndarray,
                 text:str,
                 x: int=100,
                 y: int=100,
                 scale: float = 2,
                 line_thickness: int = 4,
                 color: tuple = (0,0,0)) -> np.ndarray:

        image = self._print_double_text(image=image,
                                        text=text,
                                        x=x,
                                        y=y,
                                        scale=scale,
                                        line_thickness=int(line_thickness),
                                        color=color)
        return image

    def _print_double_text(self,
                           image: np.ndarray,
                           text: str,
                           x: int,
                           y: int,
                           scale: float,
                           line_thickness: int,
                           color: tuple) -> np.ndarray:

        if np.mean(color) > 127:
            contrast_color = (0, 0, 0)
        else:
            contrast_color = (255, 255, 255)

        cv2.putText(image,
                    text,
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    scale,
                    color,
                    int(line_thickness),
                    cv2.LINE_AA)
        cv2.putText(image,
                    text,
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    scale,
                    contrast_color,
                    int(np.floor(line_thickness*.3)),
                    cv2.LINE_AA)
        return image
