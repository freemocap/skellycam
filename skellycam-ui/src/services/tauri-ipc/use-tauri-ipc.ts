import { useMemo } from 'react';
import { tauriClient } from './tauri-client';
import { isTauri } from './tauri-detection';

/**
 * React hook — Tauri equivalent of useElectronIPC().
 * Returns { isTauri, api } where api is the typed Tauri IPC client
 * or null if not running in Tauri.
 */
export function useTauriIPC() {
    const api = useMemo(() => {
        if (!isTauri()) return null;
        return tauriClient;
    }, []);

    return {
        isTauri: isTauri(),
        api,
    };
}
