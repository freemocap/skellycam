import cv2

from skellycam.core.camera_group.camera.config.image_rotation_types import RotationTypes, \
    OPENCV_NO_ROTATION_PLACEHOLDER_VALUE


def rotate_image(image, rotation: RotationTypes):
    rotation_constant = rotation.to_opencv_constant()

    # Rotate the image if needed
    if rotation_constant is not OPENCV_NO_ROTATION_PLACEHOLDER_VALUE:
        rotated_image = cv2.rotate(image, rotation_constant)
    else:
        rotated_image = image

    return rotated_image
