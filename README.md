
<p align="center">
    <img src="https://raw.githubusercontent.com/freemocap/freemocap/main/assets/logo/freemocap-logo-black-border.svg" height="64" alt="Project Logo">
</p>
<h3 align="center">fast-camera-capture</h3>
<p align="center">📝 An easy and efficient way to connect to cameras and aggregate frame data.</p>
<p align="center">
    <a href="https://github.com/freemocap/fast-camera-capture/releases/latest">
        <img src="https://img.shields.io/github/release/freemocap/fast-camera-capture.svg" alt="Latest Release">
    </a>
    <a href="https://github.com/freemocap/fast-camera-capture/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/license-AGPL-blue.svg" alt="AGPL">
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

There are a bunch of tools out there, like OpenCV and other open source libraries that give just enough to support hardware manipulation,
but they need to be use in concert in order to be useful.

This library attempts to string those things together, and provide an interface for everyone to use in python with a simple `pip install`.

---
## Installation


### From Pip
```bash
pip install fast-camera-capture
```

### New Python developers

1) Install Python 3.10
2) Create  Virtual Environment
3) Install `fast-camera-capture`

#### To install Python 3.10

[Windows Python3 Installation Guide](https://realpython.com/installing-python/#how-to-install-from-the-full-installer)

[MacOSX Python3 Installation Guide](https://realpython.com/installing-python/#step-1-download-the-official-installer)

[Linux Python3 Installation Guide](https://computingforgeeks.com/how-to-install-python-on-ubuntu-linux-system/)

### How to use

#### Example 1 - Connecting to a Camera

[Example 1 Python Fle](fast_camera_capture/examples/example1_single_camera_connection.py) 

In this example, we connect a camera at index 0. Calling `show` allows us to view the cameras frames allowing us
to see video.

```python
from fast_camera_capture import CamArgs, Camera

if __name__ == "__main__":
    cam1 = Camera(CamArgs(webcam_id=0))
    cam1.connect()
    cam1.show()
```
___

### Contribution Guidelines

Please read our contribution doc: [CONTRIBUTING.md](CONTRIBUTING.md)

## Maintainers

* [Jon Matthis](https://github.com/jonmatthis)
* [Endurance Idehen](https://github.com/endurance)

## License
This project is licensed under the APGL License - see the [LICENSE](LICENSE) file for details.

If the AGPL does not work for your needs, we are happy to discuss terms to license this software to you with a different agreement at a price point that  increases exponentially as you move [spiritually](https://www.gnu.org/philosophy/open-source-misses-the-point.en.html) away from the `AGPL`
