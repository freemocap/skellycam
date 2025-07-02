import cv2
import numpy as np

from skellycam.core.types.image_rotation_types import  RotationTypes


def rotate_image(image:np.ndarray, rotation: RotationTypes):

    # Rotate the image if needed
    if rotation.value is not -1:
        rotated_image = cv2.rotate(image, rotation.value)
    else:
        rotated_image = image

    return rotated_image
