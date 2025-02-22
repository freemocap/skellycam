import {app, BrowserWindow} from 'electron';
import {update} from './update';
import {configureApp} from "./helpers/setup";
import {IpcManager} from "./helpers/ipc-manager";
import {WindowManager} from "./helpers/window-manager";
import {ENV_CONFIG} from "./helpers/constants";
import {PythonServer} from "./helpers/python-server";
import {LifecycleLogger} from "./helpers/logger";
import {installExtension, REACT_DEVELOPER_TOOLS, REDUX_DEVTOOLS} from 'electron-devtools-installer';

// Initialization Sequence
function startApplication() {
    LifecycleLogger.logProcessInfo();
    configureApp();
    IpcManager.initialize();

    app.whenReady()
        .then(() => {
            const mainWindow = WindowManager.createMainWindow();
            installExtension([REDUX_DEVTOOLS, REACT_DEVELOPER_TOOLS])
                .then(([redux, react]) => console.log(`Added Extensions:  ${redux.name}, ${react.name}`))
                .catch((err) => console.log('An error occurred: ', err));
            update(mainWindow);

            if (ENV_CONFIG.SHOULD_LAUNCH_PYTHON) {
                PythonServer.start();
            }
        });
}

// Lifecycle Handlers
app.on('window-all-closed', async () => {
    await PythonServer.shutdown();
    if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        WindowManager.createMainWindow();
    }
});

// Start App
startApplication();
