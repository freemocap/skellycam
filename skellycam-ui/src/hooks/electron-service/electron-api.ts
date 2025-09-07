
// Check if running in Electron
import {electronIpcClient} from "@/hooks/electron-service/electron-ipc-client";

export const isElectron = (): boolean => {
    return typeof window !== 'undefined' && !!window.electronAPI;
};

// Export the API client or null if not in Electron
export const electronAPI = isElectron() ? electronIpcClient : null;

// Type-safe wrapper hook for React components
import { useMemo } from 'react';

export function useElectronAPI() {
    const api = useMemo(() => {
        if (!isElectron()) return null;
        return electronIpcClient;
    }, []);

    return {
        isElectron: isElectron(),
        api,
    };
}
