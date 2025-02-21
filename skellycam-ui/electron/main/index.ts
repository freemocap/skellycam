import {app, BrowserWindow, ipcMain, shell} from 'electron'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import os from 'node:os'
import {update} from './update'
import {exec} from 'child_process'
import * as fs from "node:fs";

console.log('Starting Electron main process...1');
// const require = createRequire(import.meta.url)
const __dirname = path.dirname(fileURLToPath(import.meta.url))
process.env.LAUNCH_SKELLYCAM_PYTHON_SERVER = 'true';
process.env.SKELLYCAM_RUNNING_IN_ELECTRON = 'true';
process.env.SKELLYCAM_SHOULD_SHUTDOWN = 'false'; // Server will shutdown when this is set to 'true'
// The built directory structure
//
// ├─┬ dist-electron
// │ ├─┬ main
// │ │ └── index.js    > Electron-Main
// │ └─┬ preload
// │   └── index.mjs   > Preload-Scripts
// ├─┬ dist
// │ └── index.html    > Electron-Renderer
//
process.env.APP_ROOT = path.join(__dirname, '../..')

// export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron')
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist')
export const VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL
    ? path.join(process.env.APP_ROOT, 'public')
    : RENDERER_DIST

// Disable GPU Acceleration for Windows 7
if (os.release().startsWith('6.1')) app.disableHardwareAcceleration()

// Set application name for Windows 10+ notifications
if (process.platform === 'win32') app.setAppUserModelId(app.getName())

if (!app.requestSingleInstanceLock()) {
    console.log(`Another instance of the app is already running. Exiting...`);

    app.quit()
    process.exit(0)
}
console.log('Starting Electron main process...2');
let win: BrowserWindow | null = null
const preload = path.join(__dirname, '../preload/index.mjs')
const indexHtml = path.join(RENDERER_DIST, 'index.html')
let pythonServer: any = null;
let pythonServerExecutablePath = path.resolve(process.resourcesPath, 'app.asar.unpacked/skellycam_server.exe');


function checkExecutablePath() {
    console.log(`Checking python server executable path: ${pythonServerExecutablePath}`);
    if (!fs.existsSync(pythonServerExecutablePath)) {
        const originalPythonServerExecutablePath = pythonServerExecutablePath;
        pythonServerExecutablePath = path.resolve(__dirname, '../../skellycam_server.exe');
        if (!fs.existsSync(pythonServerExecutablePath)) {
            console.error(`Python server executable not found at '${pythonServerExecutablePath}' or '${originalPythonServerExecutablePath}'`);
            app.quit();
        }
    } else {
        console.log(`Python server executable found at ${pythonServerExecutablePath}`);
    }
}


function startPythonServer() {
    console.log('Starting python server...');
    checkExecutablePath();
    fs.access(pythonServerExecutablePath, fs.constants.X_OK, (err) => {
        if (err) {
            console.error(`${pythonServerExecutablePath} is not executable or accessible: ${err.message}`);
            app.quit();
        } else {
            console.log(`${pythonServerExecutablePath} is executable`);
            pythonServer = exec(`"${pythonServerExecutablePath}"`, {
                env: {
                    ...process.env,
                    PYTHONIOENCODING: 'utf-8',
                    PYTHONUTF8: '1'
                },
                maxBuffer: 1024 * 1024 // 1MB buffer size
            });
            if (!pythonServer) {
                console.error('Failed to start python server');
                app.quit();
            }
            pythonServer.stdout.on('data', (data: any) => {
                console.log(`Python server stdout: ${data}`);
            });

            pythonServer.stderr.on('data', (data: any) => {
                console.error(`Python server stderr: ${data}`);
            });
            pythonServer.on('exit', (code: any) => {
                process.env.SKELLYCAM_SHOULD_SHUTDOWN = 'true';
                console.log('Setting SKELLYCAM_SHOULD_SHUTDOWN to true');
                console.log(`Python server exited with code: ${code}`);
            });
        }
    });
}


async function createMainWindow() {
    console.log('Creating main window...')
    win = new BrowserWindow({
        title: 'Main window',
        icon: path.join(process.env.VITE_PUBLIC, 'favicon.ico'),
        width: 1280,
        height: 720,
        webPreferences: {
            preload,
            // Warning: Enable nodeIntegration and disable contextIsolation is not secure in production
            // nodeIntegration: true,

            // Consider using contextBridge.exposeInMainWorld
            // Read more on https://www.electronjs.org/docs/latest/tutorial/context-isolation
            // contextIsolation: false,
        },
    })

    if (VITE_DEV_SERVER_URL) { // #298
        win.loadURL(VITE_DEV_SERVER_URL)
        // Open devTool if the app is not packaged
        win.webContents.openDevTools()
    } else {
        win.loadFile(indexHtml)
    }

    // Test actively push message to the Electron-Renderer
    win.webContents.on('did-finish-load', () => {
        win?.webContents.send('main-process-message', new Date().toLocaleString())
    })

    // Make all links open with the browser, not with the application
    win.webContents.setWindowOpenHandler(({url}) => {
        if (url.startsWith('https:')) shell.openExternal(url)
        return {action: 'deny'}
    })


    if (process.env.LAUNCH_SKELLYCAM_PYTHON_SERVER == 'true') {
        console.log("Environment variable LAUNCH_PYTHON_SERVER is set to 'true'. Starting python server...");
        startPythonServer();
    } else {
        console.log("Environment variable LAUNCH_PYTHON_SERVER is not set to 'true'. Python server will not be started.");
    }

    // Auto update
    update(win)
}

console.log('Starting Electron main process...3');
app.whenReady().then(createMainWindow)

app.on('window-all-closed', async () => {
    if (pythonServer) {
        console.log('Shutting down python server...');
        process.env.SKELLYCAM_SHOULD_SHUTDOWN = 'true';
        console.log('Setting SKELLYCAM_SHOULD_SHUTDOWN to true from `app.on(all-windows-closed)');
        let shutdownCounter = 0;
        const maxShutdownTime = 10;
        while (shutdownCounter < maxShutdownTime && pythonServer) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            console.log(`Waiting for python server to shutdown... ${shutdownCounter++} seconds elapsed`);
            shutdownCounter++;
        }
        if (pythonServer) {
            console.error('Python server did not shutdown in time. Killing the process...');
            pythonServer.kill();
        }
        console.log('Python server shutdown.');
    }
    win = null

})

app.on('second-instance', () => {
    if (win) {
        // Focus on the main window if the user tried to open another
        if (win.isMinimized()) win.restore()
        win.focus()
    }
})

app.on('activate', () => {
    const allWindows = BrowserWindow.getAllWindows()
    if (allWindows.length) {
        allWindows[0].focus()
    } else {
        createMainWindow().then(
            () => console.log('Main window created on activate')
        ).catch(
            (e) => console.error(e)
        )
    }
})

// New window example arg: new windows url
ipcMain.handle('open-win', (_, arg) => {
    const childWindow = new BrowserWindow({
        webPreferences: {
            preload,
            nodeIntegration: true,
            contextIsolation: false,
        },
    })

    if (VITE_DEV_SERVER_URL) {
        childWindow.loadURL(`${VITE_DEV_SERVER_URL}#${arg}`)
    } else {
        childWindow.loadFile(indexHtml, {hash: arg})
    }
})

console.log('Starting Electron main process...4');
