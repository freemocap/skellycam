import { BrowserWindow, shell } from 'electron';
import {APP_PATHS, ENV_CONFIG} from "./constants";

export class WindowManager {
  static createMainWindow() {
    const window = new BrowserWindow({
      title: 'Skellycam 💀📸',
      icon: APP_PATHS.SKELLYCAM_ICON_PATH,
      width: 1280,
      height: 720,
      webPreferences: {
        preload: APP_PATHS.PRELOAD,
        contextIsolation: true,
        nodeIntegration: false
      }
    });

    this.configureWindowHandlers(window);
    this.loadContent(window);

    return window;
  }

  private static configureWindowHandlers(window: BrowserWindow) {
    window.webContents.on('did-finish-load', () => {
      window.webContents.send('app-ready', Date.now());
    });

    window.webContents.setWindowOpenHandler(({ url }) => {
      if (url.startsWith('https:')) shell.openExternal(url);
      return { action: 'deny' };
    });
  }

  private static loadContent(window: BrowserWindow) {
    ENV_CONFIG.IS_DEV
      ? window.loadURL(process.env.VITE_DEV_SERVER_URL!)
      : window.loadFile(APP_PATHS.RENDERER_HTML);

    if (ENV_CONFIG.IS_DEV) {
      window.webContents.openDevTools();
    }
  }
}