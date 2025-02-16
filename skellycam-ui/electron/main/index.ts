import {app, BrowserWindow, ipcMain, shell} from 'electron'
import {createRequire} from 'node:module'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import os from 'node:os'
import {update} from './update'
import {exec} from 'child_process'
import * as fs from "node:fs";

const require = createRequire(import.meta.url)
const __dirname = path.dirname(fileURLToPath(import.meta.url))

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
    app.quit()
    process.exit(0)
}

let win: BrowserWindow | null = null
const preload = path.join(__dirname, '../preload/index.mjs')
const indexHtml = path.join(RENDERER_DIST, 'index.html')
let pythonServer: any;
let pythonServerExectuablePath = path.resolve(process.resourcesPath, 'app.asar.unpacked/python-binary/windows/skellycam-server.exe');

// Check executable existence
if (!fs.existsSync(pythonServerExectuablePath)) {
    console.error(`Python server executable not found at ${pythonServerExectuablePath}`);
    pythonServerExectuablePath = path.resolve(__dirname, '../../python-binary/windows/skellycam-server.exe');
    if (!fs.existsSync(pythonServerExectuablePath)) {
        console.error(`Python server executable not found at ${pythonServerExectuablePath} either`);
    }
    app.quit();
} else {
    console.log(`Python server executable found at ${pythonServerExectuablePath}`);
}
fs.access(pythonServerExectuablePath, fs.constants.X_OK, (err) => {
    if (err) {
        console.error(`${pythonServerExectuablePath} is not executable or accessible: ${err.message}`);
        app.quit();
    } else {
        console.log(`${pythonServerExectuablePath} is executable`);
    }
});


require('fs').access(pythonServerExectuablePath, require('fs').constants.X_OK, (err: { message: any }) => {
    if (err) {
        console.error(`${pythonServerExectuablePath} is not executable or accessible: ${err.message}`);
    } else {
        console.log(`${pythonServerExectuablePath} is executable`);
    }
});

async function createWindow() {
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

    // Start the Python server
    const pythonServer = exec(`"${pythonServerExectuablePath}"`, {
            env: {
                ...process.env,
                PYTHONIOENCODING: 'utf-8',
                PYTHONUTF8: '1'
            }
        },
        (error, stdout, stderr) => {
            if (error) {
                console.error(`Error starting Python server: ${error.message}`);
                return;
            }
            console.log(`Python server stdout: ${stdout}`);
            if (stderr) console.error(`Python server stderr: ${stderr}`);
        });

    pythonServer.on('exit', (code) => {
        console.log(`Python server exited with code: ${code}`);
    });

    // Auto update
    update(win)
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
    if (pythonServer) {
        console.log('Killing python server...');
        pythonServer.kill();
        console.log('Python server shutdown.');
    }
    win = null
    if (process.platform !== 'darwin') app.quit()

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
        createWindow()
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
