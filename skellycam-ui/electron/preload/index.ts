import { contextBridge, ipcRenderer } from 'electron';

// Expose a simple tRPC bridge + menu action listener + menu label updater
contextBridge.exposeInMainWorld('electronAPI', {
    invoke: (path: string, input?: unknown) =>
        ipcRenderer.invoke('trpc', { path, input }),

    onMenuAction: (callback: (action: string) => void) => {
        const handler = (_event: Electron.IpcRendererEvent, action: string) => {
            callback(action);
        };
        ipcRenderer.on('menu-action', handler);

        // Return a cleanup function to remove the listener
        return () => {
            ipcRenderer.removeListener('menu-action', handler);
        };
    },

    sendMenuLabels: (params: Record<string, unknown>) => {
        ipcRenderer.send('update-menu-labels', params);
    },
});
