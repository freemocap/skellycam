<p align="center">
    <img src="https://github.com/user-attachments/assets/55dea5bb-6823-4773-b41e-a43a4d84c2ba" height="240" alt="SkellyCam Logo">
</p>

<h3 align="center">SkellyCam</h3>
<p align="center"> The camera backend for the FreeMoCap Project 💀📸</p>
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

This iteration of SkellyCam operates with an [Tauri](https://tauri.app) application. The frontend UI is built using Nuxt
and VueJS, and the backend code that connects to cameras, pulls synchronized images, saves videos, etc is build in
Python hosted behind a Uvicorn/FastAPI server.

Although we *could* run all the camera connections via the `MediaDevices` API exposed in the frontend, those processes
are primarily optimized for high efficiency video *streams* which abstract away from the actual moments of pulling
images from the camera devices, which makes it very hard to produce the kind of high-accuracy software based
synchronization necessary for the `freemocap` software.

Handling the multicamera connections in Python is difficult, and much effort is expended to ensure the images pulled
from each camera synchronously and at the highest possible framerate (without blocking or bogging from other operations
in the software). Image data is passed between processes using a complex combination of shared memory, multiprocessing
PIPEs, and a websocket connection to feed images to a Client frontend.

Copious logging (log level set in `skellycam/__init__.py`) and high precision timestamp logs have and will continue to
allow for deeper debugging and streamlining of the framereading processes that will pour empirical data into he
`freemocap` light-to-skeleton building pipeline.

## Running Skellycam Installation

> [!TIP]
> Run the following commands from the project root directory (i.e the same directory as this `README.md` file)

You have two options to run two separate and variously broken version of this software:

### Option 1. Run the pure Python code with a QT GUI:

This method will pop up a mostly functional QT GUI that can detect, connect to, and record videos from the FastAPI
server. Mostly functional, but I think might occasionally crash (I think) due to some concurrency problem updating
something in the QT code?

It runs pretty well, but there's FPS drop on `record`, which I suspect is fixable by fiddling with things in the
`FrameWrangler` class (see #TODO comments in there).

To run the pure python skellycam:

0 . ensure you have [Poetry](https://python-poetry.org/) installed and run: the following command:

1. Create python virtual environment and install dependencies:

```
poetry shell
```

2. Run `skellycam/__main__.py` with the `--qt` flag, or just:

```
poetry run skellycam --qt
```

A big friendly skeleton should pop up and offer various camera based services. Click around the big friendly buttons and
keep an eye on the terminal for useful output. Videos are saved to a `~/skellycam/recordings/` folder in your Home
directory (i.e. wheteever returns from `pathlib.Path.home()`)

### Option 2: Build a Python executable and run the Tauri/Nuxt/Vue app:

This options will create a Tauri application that runs the Python backend as a sidecar, and the Nuxt/Vue frontend in a
Tauri wrangled browser window. With any luck, this currently barely functional version will be the basis of the
`freemocap v2.0` architecture.


> [!TIP]
> tl;dr Tauri/Nuxt - Quickstart
> 
> 0. Install pre-reqs
> 1. Build Python binary: `poetry run pyinstaller`
> 2. Install Node/Tauri stuff - `npm install`
> 3. Run in dev mode: `npm run dev`
> - OR-
> 4. Build installer: `npm run build`

### Detailed Tauri/Nuxt install instructions
#### 0. Install pre-requisites
- Install Rust on your system - https://www.rust-lang.org/tools/install
- Install Node.js - https://nodejs.org/en

#### 1. Build Python executable for Tauri sidecar

**To generate the python sidecar executable, run the command (note, it takes a while):**

```
poetry run pyinstaller
```

We build the Python backend code (i.e. the uvicorn/fastapi api server) into a binary executable using [
`pyinstaller`](skellycam/utilities/build_pyinstaller_executable.py). This binary will be loaded and run as
a ['sidecar'](https://tauri.app/v1/guides/building/sidecar/) in the Tauri app.

The executable will be saved to the `skellycam/dist/` folder, with a 'target triple suffix' appended to the file name
based on the OS it was built on (see 'sidecar' link above for some terse details).

The path to this binary (minus the target triple and extension) must be specified in a few spots in the
`src-tauri/tauri.conf.json` file (path relative to that file), as well in the `side_car_base_name` variable specified in
the `src-tauri/src/main.rs` file.



#### 2. Install Node/Nuxt/Tauri stuff

```
npm install
```
> [!NOTE]
> The `postinstall` script in `package.json` cd's into the `skellycam-ui/` folder an runs `npm install` in there

### 3. Running the application in `dev` mode

To build and run the Tauri application in `dev`mode, run this command:
```
npm run dev
```

This should build the Rust backend, launch the nuxt/vue based frontend from `skellycam-ui` in a new window, and run the
python server sidecar. Check the terminal for relevant `localhost` urls

> [!TIP]
> If you are working on the python code and want to see changes without rebuilding the pyinstaller sidecar, simply run
`skellycam/__main__.py` after the Tauri app has aleady started. It will kill the `sidecar` program and take over serving
> responses on that port
> (I don't know if thats, like, the right way to do that, but it works for now ¯\\_(ツ)_/¯

whee! It doesn't do much, but if you click the `Connect to Websocket` button followed by the `Connect to Cameras`
button, it should detect and connect to all available cameras, and show a the images from each window in a sloppy grid.

#### BONUS - Building an installer

> [!WARNING]
> This produces installers and stuff, which is cool, but the resulting application crashes immediately, which is notably
> less cool.

To produce installers and whatnot, run:

```
npm run build
```

This process is triggered automatically on commit based on the Github Actions workflow defined in
`.github/workflows/build_executables` Those don't work either, but whatreya gonna do ¯\\\_(ツ)_/¯


## License

This project is licensed under the APGL License - see the [LICENSE](LICENSE) file for details.

If the AGPL does not work for your needs, we are happy to discuss terms to license this software to you with a different
agreement at a price point that increases exponentially as you
move [spiritually](https://www.gnu.org/philosophy/open-source-misses-the-point.en.html) away from the `AGPL`
