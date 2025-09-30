import { contextBridge, ipcRenderer } from 'electron'

export interface FrameData {
  buffer: Buffer
  // Main process metrics
  mainReadFps: number
  mainReadFrameCount: number
  mainTotalBytesRead: number
}

export interface MainProcessStats {
  readFrameCount: number
  readFps: number
  totalBytesRead: number
  avgReadTimeMs: number
}

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Start reading the file in the main process
  startFileReader: async (filePath: string, pollRateMs: number): Promise<{ success: boolean }> => {
    return await ipcRenderer.invoke('start-file-reader', filePath, pollRateMs)
  },

  // Stop reading the file
  stopFileReader: async (): Promise<{ success: boolean }> => {
    return await ipcRenderer.invoke('stop-file-reader')
  },

  // Get current main process read statistics
  getMainProcessStats: async (): Promise<MainProcessStats> => {
    return await ipcRenderer.invoke('get-main-process-stats')
  },

  // Listen for frame data from main process
  onFrameData: (callback: (data: FrameData) => void): void => {
    ipcRenderer.on('frame-data', (_event, data: FrameData) => {
      callback(data)
    })
  },

  // Remove frame data listener
  removeFrameDataListener: (): void => {
    ipcRenderer.removeAllListeners('frame-data')
  }
})

// Type declaration for TypeScript
declare global {
  interface Window {
    electronAPI: {
      startFileReader: (filePath: string, pollRateMs: number) => Promise<{ success: boolean }>
      stopFileReader: () => Promise<{ success: boolean }>
      getMainProcessStats: () => Promise<MainProcessStats>
      onFrameData: (callback: (data: FrameData) => void) => void
      removeFrameDataListener: () => void
    }
  }
}
