import { contextBridge, ipcRenderer } from 'electron'
import * as fs from 'fs'

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  readFile: (filePath: string): Buffer => {
    return fs.readFileSync(filePath)
  },

  fileExists: (filePath: string): boolean => {
    return fs.existsSync(filePath)
  },

  onFileUpdate: (callback: () => void) => {
    ipcRenderer.on('file-updated', callback)
  },

  removeFileUpdateListener: (callback: () => void) => {
    ipcRenderer.removeListener('file-updated', callback)
  }
})

// Type declaration for TypeScript
declare global {
  interface Window {
    electronAPI: {
      readFile: (filePath: string) => Buffer
      fileExists: (filePath: string) => boolean
      onFileUpdate: (callback: () => void) => void
      removeFileUpdateListener: (callback: () => void) => void
    }
  }
}
