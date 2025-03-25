import {ipcMain} from 'electron';
import {WindowManager} from "./window-manager";
import {PythonServer} from "./python-server";
import {dialog} from 'electron';

export class IpcManager {
    static initialize() {
        this.handleWindowControls();
        this.handlePythonControls();
        this.handleFileSystemControls();
    }

    private static handleWindowControls() {
        ipcMain.handle('open-child-window', (_, route) => {
            console.log('Opening child window with route:', route);
            const child = WindowManager.createMainWindow();
            child.loadURL(`${process.env.VITE_DEV_SERVER_URL}#${route}`);
        });
    }
    private static handleFileSystemControls() {
        ipcMain.handle('select-directory', async () => {
            const result = await dialog.showOpenDialog({
                properties: ['openDirectory']
            });

            if (!result.canceled && result.filePaths.length > 0) {
                return result.filePaths[0];
            }
            return null;
        });
    }
    private static handlePythonControls() {
        ipcMain.handle('restart-python-server', () => {
            console.log('Restarting Python Server');
            PythonServer.shutdown();
            PythonServer.start();
        });
    }
}
