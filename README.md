
<p align="center">
    <img src="https://github.com/freemocap/skellycam/blob/main/skellycam/assets/logo/skelly-cam-logo.svg" height="128" alt="Project Logo">
</p>
<h3 align="center">SkellyCam</h3>
<p align="center"> An easy and efficient way to connect to one or more cameras and record synchronized videos 💀📸</p>
<p align="center">
    <a href="https://github.com/freemocap/fast-camera-capture/releases/latest">
        <img src="https://img.shields.io/github/release/freemocap/fast-camera-capture.svg" alt="Latest Release">
    </a>
    <a href="https://github.com/freemocap/fast-camera-capture/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/license-AGPLv3+-blue.svg" alt="AGPLv3+">
    </a>
    <a href="https://github.com/freemocap/fast-camera-capture/issues">
        <img src="https://img.shields.io/badge/contributions-almost-ff69b4.svg" alt="Contributions Welcome">
    </a>
  <a href="https://github.com/psf/black">
    <img alt="https://img.shields.io/badge/code%20style-black-000000.svg" src="https://img.shields.io/badge/code%20style-black-000000.svg">
  </a>
</p>


---
## Motivation

Connecting to cameras on multiple platforms in a way that is not slow is a difficult challenge, especially for new developers.

There are a bunch of tools out there (e.g. OpenCV) and other open source libraries that give just enough to support hardware manipulation,
but they need to be use in concert in order to be useful.

This library attempts to string those things together, and provide an interface for everyone to use in python with a simple `pip install`.

The primary focus is to provide an easy method to connect to one or more cameras and provide methods for streaming/recordig synchronized frames from the connected cameras.



> **NOTE** - The SkellyCam package is the primary camera backend for the `freemocap` markeless motion capture software 💀✨
> 
> [https:github.com/freemocap/freemocap](https:github.com/freemocap/freemocap)
> 
>[https://freemocap.org](https://freemocap.org)

---
## Installation and Usage

### 0. Open a terminal (ideally with a `python` virtual environment activate) 

### 1. Install from Pip
Enter the command below and press 'Enter'
```bash
pip install skellycam
```

### 2. Launch SkellyCam GUI
Enter the command below and press 'Enter'
```bash
skellycam
```


### 3. Success! 💀📸✨
Hopefully a bunch of text scrolled by and a GUI popped up! 

If not, please [open an issue on the github repo](https://github.com/freemocap/skellycam/issues) and we'll try to help you out :) 


## Limitation (aka TO DO)  -
- Currently uses `opencv` to connect to cameras, so it won't recognize hardware that can't be connected with `cv2.VideoCapture` - Support for other camera hardware (e.g. FLIR) coming soon
- Camera streams are not synchronized at run time, but are saved and synchronized after the fact. This is time-consuming process that requres frames be saved in RAM until the recording is done. Both of these weaknesses have solutions in the works.

### New Python developers

1) Install Python 3.10
2) Create  Virtual Environment
3) Install `skellycam`

#### To install Python 3.10

[Windows Python3 Installation Guide](https://realpython.com/installing-python/#how-to-install-from-the-full-installer)

[MacOSX Python3 Installation Guide](https://realpython.com/installing-python/#step-1-download-the-official-installer)

[Linux Python3 Installation Guide](https://computingforgeeks.com/how-to-install-python-on-ubuntu-linux-system/)

### How to use

#### RECOMMENDED -  Use the GUI!

Launch the GUI by running `skellycam` in a terminal. 

This is currently the most tested method for interacting with the cameras.


#### Example 1 - Connecting to a single Camera and showing the video feed

[Example 1 Python Fle](skellycam/examples/example1_single_camera_connection.py)

In this example, we connect a camera at index 0. Calling `show` allows us to view the cameras frames allowing us
to see video.

> NOTE - Work in progress, no clean way to kill this window yet

```python
from skellycam import CameraConfig, Camera

if __name__ == "__main__":
    cam1 = Camera(CameraConfig(cam_id=0))
    cam1.connect()
    cam1.show()
```


#### Example 2 - Connect to all available cameras and record synchronized videos

> NOTE - Experimental and under development, might be unstable
 
[Example 2 Python Fle](skellycam/examples/example1_single_camera_connection.py)
```python
from skellycam.experiments import MultiCameraVideoRecorder

if __name__ == "__main__":

    synchronized_video_recorder = MultiCameraVideoRecorder()
    synchronized_video_recorder.run()

```

### Contribution Guidelines

Please read our contribution doc: [CONTRIBUTING.md](CONTRIBUTING.md)

## Maintainers

* [Jon Matthis](https://github.com/jonmatthis)
* [Endurance Idehen](https://github.com/endurance)

## License
This project is licensed under the APGL License - see the [LICENSE](LICENSE) file for details.

If the AGPL does not work for your needs, we are happy to discuss terms to license this software to you with a different agreement at a price point that  increases exponentially as you move [spiritually](https://www.gnu.org/philosophy/open-source-misses-the-point.en.html) away from the `AGPL`
