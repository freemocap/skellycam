# SPECIAL INSTRUCTIONS FOR THE `jon/development` BRANCH 

## Installation


### Python Fastapi/Uvicorn server
0. Install `uv` 
   - https://github.com/astral-sh/uv?tab=readme-ov-file#installation
1. clone the repo 
   - `git clone https://github.com/freemocap/skellycam`
2. Change directory to the repo: 
   - `cd skellycam`
3. **Change to the `jon/development` branch:**
   - `git switch jon/development`
4. Create virtual environment: 
   - `uv venv`
5. Activate virtual environment
   - Windows: `.venv/bin/activate`
   - Mac/Linux: `source .venv/bin/activate`
6. Install dependencies
  - `uv sync`

##### Linux only (?)
You need to install `clang` and `portaudio` to get the audio recording stuff to work.
```
sudo apt update
sudo apt install clang
sudo apt install portaudio19-dev
```

### React/Electron UI

#### Pre-requisites
- install Node.js and npm
  - https://nodejs.org/en/download/

#### Installation
1. Change to the `skellycam-ui` directory
- `cd skellycam-ui`
- `npm install`

#### Running the UI in development mode
- `npm run dev`


   
## Run the SkellyCam application (FastAPI/Uvicorn server) 
1. - `python skellycam/__main__.py`
   - The server should start on `http://localhost:8006`


# Build installer
0. `cd skellycam-ui`
1. Build Python installer with Nuitka  
- `../installers/nutika_scripts/nuitka_installer_windows.bat`
- NOTE - Mac and Linux installer scripts should presumably work without much effort, but haven't don't that yet
- This step can take up to an hour and results in an executable called `skellycam_server[.exe]` in the `skellycam-ui/` folder
2. Build electron app (which bundles the python server executable from the previous step
- `npm install`
- `npm run build`

If all went well, the installer will be in `/skellycam-ui/releases/[version-number]/skellycam_[version-number]_installer[.exe]`!
---
---
# STANDARD README CONTINUES BELOW
___
___
___











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


## License

This project is licensed under the APGL License - see the [LICENSE](LICENSE) file for details.

If the AGPL does not work for your needs, we are happy to discuss terms to license this software to you with a different
agreement at a price point that increases exponentially as you
move [spiritually](https://www.gnu.org/philosophy/open-source-misses-the-point.en.html) away from the `AGPL`
