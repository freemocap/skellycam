// Type declarations for Electron API exposed via preload

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

export {}
