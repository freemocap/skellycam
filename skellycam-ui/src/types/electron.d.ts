declare global {
    interface Window {
        electronAPI: {
            selectDirectory: () => Promise<string | null>;
            // Add other electron APIs here as needed
        }
        ipcRenderer: {
            on: (channel: string, func: (...args: any[]) => void) => void;
            off: (channel: string, func: (...args: any[]) => void) => void;
            send: (channel: string, ...args: any[]) => void;
            invoke: (channel: string, ...args: any[]) => Promise<any>;
        }
    }
}

// This export is needed to make this a module
export {}
