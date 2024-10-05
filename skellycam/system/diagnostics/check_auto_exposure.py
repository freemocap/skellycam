import platform
from typing import Union

import cv2
import numpy as np

MIN_EXPOSURE = -9
MAX_EXPOSURE = -5
DEFAULT_EXPOSURE = -6

EXPOSURE_SETTINGS = [DEFAULT_EXPOSURE, 'AUTO']
EXPOSURE_SETTINGS.extend(list(range(MIN_EXPOSURE, MAX_EXPOSURE + 1)))

HYPOTHETICAL_AUTO_EXPOSURE_SETTINGS = [0.75, 3]
HYPOTHETICAL_MANUAL_EXPOSURE_SETTINGS = [0.25, 1]

def run_frame_loop(cap: cv2.VideoCapture, exposure_setting: int, auto_manual_setting:str, frames: int = 10) -> dict:
    """Capture the mean brightness of frames from the video capture device.

    Parameters
    ----------
    cap : cv2.VideoCapture
        The video capture device.
    frames : int, optional
        Number of frames to capture, by default 30.

    Returns
    -------
    dict
        Dictionary with mean and standard deviation of brightness.
    """

    brightness_values = []
    r = np.random.randint(0, 99999)# big number to keep window name unique
    for fr in range(frames):
        success, image = cap.read()
        if not success:
            print("Failed to capture frame, breaking frame loop")
            break
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = .5
        color = (255, 0, 255)  # FFOOFF!
        thickness = 2
        position = (10, 30)  # top-left corner
        position2 = (10, 60)  # top-left corner

        # Add text to the image
        #put transparent rect under text for legibility
        annotated_image = image.copy()
        cv2.rectangle(annotated_image, (0, 0), (300, 80), (255, 255, 255, .2), -1)
        cv2.putText(annotated_image, f"(Fr#{fr}) Auto/Man: {auto_manual_setting}, Set: {exposure_setting}, Actual: {cap.get(cv2.CAP_PROP_EXPOSURE)}", position, font, font_scale, color, thickness)
        cv2.putText(annotated_image, f"`np.mean(image)={np.mean(image):.2f}", position2, font, font_scale, color, thickness)

        cv2.imshow(f"{r}Brightness Calibration (q to quit)", annotated_image)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        if not success:
            continue
        brightness_values.append(np.mean(image))
    return {
        "mean": np.mean(np.asarray(brightness_values)),
        "median": np.median(np.asarray(brightness_values)),
        "std": np.std(np.asarray(brightness_values))
    }



def main():
    if platform.system() == "Windows":
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(0, cv2.CAP_ANY)

    print(f"Exposure on init: {cap.get(cv2.CAP_PROP_EXPOSURE)}")
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)

    results = []
    # Initial capture to let the webcam settle
    for auto_exposure_setting, manual_exposure_setting in zip(HYPOTHETICAL_AUTO_EXPOSURE_SETTINGS, HYPOTHETICAL_MANUAL_EXPOSURE_SETTINGS):
        print(f"\n-----------------------\nUsing `{auto_exposure_setting}` to enable auto exposure and `{manual_exposure_setting}` to enable manual exposure...")
        for _ in range(30):
            success, image = cap.read() # let it settle for a bit
        print(f"Auto Exposure before set: {cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)}")


        for exposure_setting in EXPOSURE_SETTINGS:
            if exposure_setting =='AUTO':
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_exposure_setting)
                print(f"Auto Exposure after set to {auto_exposure_setting}: {cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)} (hypothetically auto exposure)")
            else:
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, manual_exposure_setting)
                print(f"Auto Exposure after set to {manual_exposure_setting}: {cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)} (hypothetically manual exposure)")

            results = run_brightness_test(auto_exposure_setting=auto_exposure_setting,
                                          cap = cap,
                                          exposure_setting = exposure_setting,
                                          manual_exposure_setting = manual_exposure_setting,
                                          results=results)



    # Print the results as a table
    headers = ["(SetAuto, SetManual)", "Exposure", "Mean Brightness", "Median", "Std Dev"]
    header_format = "{:<20} {:<15} {:<20} {:<20} {:<20}"
    row_format = "{:<20}  {:<15} {:<20.1f} {:<20.1f} {:<20.1f}"
    print(header_format.format(*headers))
    print("-" * 75)
    prev = results[0]
    for row in results:
        if row[0] != prev[0]:
            print("\n")
        print(row_format.format(*row))
        prev = row

    cap.release()




def run_brightness_test(auto_exposure_setting: float,
                        cap: cv2.VideoCapture,
                        exposure_setting: Union[str,int],
                        manual_exposure_setting: float,
                        results: list) -> list:
    if not exposure_setting == 'AUTO':
        cap.set(cv2.CAP_PROP_EXPOSURE, exposure_setting)


    exposure = cap.get(cv2.CAP_PROP_EXPOSURE)
    print(f"Exposure after set to {exposure_setting}: {exposure}")
    brightness_data = run_frame_loop(cap=cap, exposure_setting=exposure_setting, auto_manual_setting=str(f"({auto_exposure_setting}, {manual_exposure_setting}"))
    results.append([f"({auto_exposure_setting},{manual_exposure_setting})", exposure_setting,
                    brightness_data["mean"], brightness_data["median"], brightness_data["std"]])
    return results

if __name__ == "__main__":
    main()