import path from 'node:path';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const APP_PATHS = {
    PRELOAD: path.join(__dirname,'../preload/index.mjs'),
  RENDERER_HTML: path.join(__dirname, '../../dist/index.html'),
    PYTHON_SERVER_EXECUTABLE_PATH: path.resolve(process.resourcesPath, 'app.asar.unpacked/skellycam_server.exe'),
    PYTHON_SERVER_EXECUTABLE_DEV: path.resolve(__dirname, '../../skellycam_server.exe'),
    SKELLYCAM_ICON_PATH: path.resolve(__dirname, '../../../shared/skellycam-logo/skellycam-favicon.ico')

};

export const ENV_CONFIG = {
    IS_DEV: process.env.NODE_ENV === 'development',
    SHOULD_LAUNCH_PYTHON: process.env.LAUNCH_SKELLYCAM_PYTHON_SERVER === 'true'
};
const checkAppPaths = () => {
    Object.entries(APP_PATHS).forEach(([key, path]) => {
        if (fs.existsSync(path)) {
            console.log(`✓ ${key} exists at ${path}`);
        } else {
            console.log(`✗ ${key} does not exist at ${path}`);
        }
    });
};

checkAppPaths()