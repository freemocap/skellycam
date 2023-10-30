from pathlib import Path

import cv2

from skellycam.utils.start_file import open_file


def plot_first_middle_and_last_frames(
        synchronized_frame_list_dictionary,
        path_to_save_plots_png,
        first_frame_number: int = 0,
        end_frame_number: int = -1,
        open_image_after_saving: bool = False,
):
    import matplotlib.pyplot as plt

    if end_frame_number == -1:
        end_frame_number = len(list(synchronized_frame_list_dictionary.values())[0])

    middle_frame_number = (end_frame_number - first_frame_number) // 2

    number_of_cameras = len(synchronized_frame_list_dictionary)

    fig = plt.Figure(figsize=(10, 10))

    session_name = Path(path_to_save_plots_png).parent.parent.parent.stem
    recording_name = Path(path_to_save_plots_png).parent.parent.stem
    fig.suptitle(f"Timestamps of synchronized frames\nsession: {session_name}, recording: {recording_name}")

    for camera_number, item in enumerate(synchronized_frame_list_dictionary.items()):
        camera_id, frame_payload_list = item

        first_frame = cv2.cvtColor(frame_payload_list[first_frame_number].image, cv2.COLOR_BGR2RGB)
        mid_frame = cv2.cvtColor(frame_payload_list[middle_frame_number].image, cv2.COLOR_BGR2RGB)
        last_frame = cv2.cvtColor(frame_payload_list[end_frame_number - 1].image, cv2.COLOR_BGR2RGB)

        number_of_columns = 3
        first_frame_ax = fig.add_subplot(number_of_cameras, number_of_columns, (camera_number * number_of_columns) + 1)
        first_frame_ax.imshow(first_frame)
        if camera_number == 0:
            first_frame_ax.set_title(f"First frame (frame number: {first_frame_number})")
        first_frame_ax.set_xticks([])
        first_frame_ax.set_yticks([])
        first_frame_ax.set_ylabel(f"Camera {camera_id}")

        mid_frame_ax = fig.add_subplot(number_of_cameras, number_of_columns, (camera_number * number_of_columns) + 2)
        mid_frame_ax.imshow(mid_frame)
        mid_frame_ax.set_xticks([])
        mid_frame_ax.set_yticks([])
        if camera_number == 0:
            mid_frame_ax.set_title(f"Middle frame (frame number: {middle_frame_number})")

        last_frame_ax = fig.add_subplot(number_of_cameras, number_of_columns, (camera_number * number_of_columns) + 3)
        last_frame_ax.imshow(last_frame)
        last_frame_ax.set_xticks([])
        last_frame_ax.set_yticks([])
        if camera_number == 0:
            last_frame_ax.set_title(f"Last frame (frame number: {end_frame_number - 1})")
    fig.tight_layout()
    fig.savefig(path_to_save_plots_png)

    if open_image_after_saving:
        open_file(path_to_save_plots_png)
