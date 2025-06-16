import cv2

from skellycam.core.types.image_rotation_types import OPENCV_NO_ROTATION_PLACEHOLDER_VALUE, RotationTypes


def rotate_image(image, rotation: RotationTypes):
    rotation_constant = rotation.to_opencv_constant()

    # Rotate the image if needed
    if rotation_constant is not OPENCV_NO_ROTATION_PLACEHOLDER_VALUE:
        rotated_image = cv2.rotate(image, rotation_constant)
    else:
        rotated_image = image

    return rotated_image
