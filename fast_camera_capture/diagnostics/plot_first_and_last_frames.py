import os


def plot_first_and_last_frames(
    synchronized_frame_list_dictionary,
    path_to_save_plots_png,
    open_image_after_saving: bool = False,
):
    import matplotlib.pyplot as plt

    number_of_cameras = len(synchronized_frame_list_dictionary)
    fig = plt.Figure(figsize=(10, 10))

    for cam_id, frame_payload_list in synchronized_frame_list_dictionary.items():

        first_frame = frame_payload_list[0].image
        last_frame = frame_payload_list[-1].image

        first_frame_ax = fig.add_subplot(number_of_cameras, 2, (int(cam_id) * 2) + 1)
        first_frame_ax.imshow(first_frame)
        first_frame_ax.set_title(f"First frame - Camera {cam_id}")

        last_frame_ax = fig.add_subplot(number_of_cameras, 2, (int(cam_id) * 2) + 2)
        last_frame_ax.imshow(last_frame)
        last_frame_ax.set_title(f"Last frame - Camera {cam_id}")

    fig.savefig(path_to_save_plots_png)

    if open_image_after_saving:
        os.startfile(path_to_save_plots_png, "open")
