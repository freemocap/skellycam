import { ipcMain } from 'electron';
import {WindowManager} from "./window-manager";
import {PythonServer} from "./python-server";

export class IpcManager {
  static initialize() {
    this.handleWindowControls();
    this.handlePythonControls();
  }

  private static handleWindowControls() {
    ipcMain.handle('open-child-window', (_, route) => {
      const child = WindowManager.createMainWindow();
      child.loadURL(`${process.env.VITE_DEV_SERVER_URL}#${route}`);
    });
  }

  private static handlePythonControls() {
    ipcMain.handle('restart-python-server', () => {
      PythonServer.shutdown();
      PythonServer.start();
    });
  }
}