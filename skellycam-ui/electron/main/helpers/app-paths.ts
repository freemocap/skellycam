import path from "node:path";
import {fileURLToPath} from "node:url";
import {app} from "electron";

export const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Function to get the correct resources path based on environment
const getResourcesPath = () => {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'app.asar.unpacked');
  } else {
    return path.join(__dirname, '../../');
  }
};
export const APP_PATHS = {
    PRELOAD: path.join(__dirname, '../preload/index.mjs'),
    RENDERER_HTML: path.join(__dirname, '../../dist/index.html'),
    PYTHON_SERVER_EXECUTABLE_PATH_DEV: path.join(getResourcesPath(), '../dist/skellycam_server.exe'),
    PYTHON_SERVER_EXECUTABLE_PATH_WINDOWS_INSTALL: path.join(app.getPath('home'), 'AppData/Local/Programs/skellycam/resources/app.asar.unpacked/skellycam_server.exe'),
    SKELLYCAM_ICON_PATH: path.resolve(__dirname, '../../../shared/skellycam-logo/skellycam-favicon.ico'),
    SKELLYCAM_PNG_PATH: path.resolve(__dirname, '../../../shared/skellycam-logo/skellycam-logo.png'),
    CONFIG_PATH: path.resolve(__dirname, '../../../shared/app_settings.json')
};
