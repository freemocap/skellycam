
// Check if running in Electron
import {electronIpcClient} from "@/services/electron-ipc/electron-ipc-client";
import { tauriTrpcClient } from "@/services/tauri-ipc/tauri-trpc-shim";
import { isTauri } from "@/services/tauri-ipc/tauri-detection";

export const isElectron = (): boolean => {
    return typeof window !== 'undefined' && !!window.electronAPI;
};

// Export the API client or null if not in Electron/Tauri
export const electronIpc = isElectron()
    ? electronIpcClient
    : isTauri()
        ? tauriTrpcClient
        : null;

// Type-safe wrapper hook for React components
import { useMemo } from 'react';

export function useElectronIPC() {
    const api = useMemo(() => {
        if (isElectron()) return electronIpcClient;
        if (isTauri()) return tauriTrpcClient;
        return null;
    }, []);

    return {
        isElectron: isElectron() || isTauri(),
        api,
    };
}
