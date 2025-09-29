import { app, BrowserWindow } from 'electron'
import { join } from 'path'
import { is } from '@electron-toolkit/utils'

let mainWindow: BrowserWindow | null = null

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    }
  })

  // Load the app using electron-toolkit's is.dev helper
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    // Development mode - load from vite dev server
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
    mainWindow.webContents.openDevTools()
  } else {
    // Production mode - load from built files
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  mainWindow.on('closed', (): void => {
    mainWindow = null
  })
}

app.whenReady().then((): void => {
  createWindow()

  app.on('activate', (): void => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', (): void => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
