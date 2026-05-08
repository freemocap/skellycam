import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';
import type {
    ExecutableCandidate,
    ProcessInfo,
    FolderEntry,
    FetchOptions,
    FetchResponse,
} from './tauri-types';

// ── Typed Tauri IPC client ────────────────────────────────────
// Mirrors the shape of the old tRPC Electron client so existing
// components continue to work with minimal changes.

export const tauriClient = {
    pythonServer: {
        start: (input: { exePath: string | null }) =>
            invoke<void>('start_python_server', { exePath: input.exePath }),

        stop: () => invoke<void>('stop_python_server'),

        getExecutablePath: () =>
            invoke<string | null>('get_executable_path'),

        getExecutableCandidates: () =>
            invoke<ExecutableCandidate[]>('get_executable_candidates'),

        refreshCandidates: () =>
            invoke<ExecutableCandidate[]>('refresh_candidates'),

        isRunning: () => invoke<boolean>('is_python_server_running'),

        getProcessInfo: () =>
            invoke<ProcessInfo | null>('get_process_info'),
    },

    fileSystem: {
        /** Uses Tauri dialog plugin directly from JS */
        selectDirectory: async (): Promise<string | null> => {
            const result = await open({ directory: true });
            return typeof result === 'string' ? result : null;
        },

        openFolder: (input: { path: string }) =>
            invoke<boolean>('open_folder', { path: input.path }),

        getHomeDirectory: () => invoke<string>('get_home_directory'),

        getFolderContents: (input: { path: string }) =>
            invoke<FolderEntry[]>('get_folder_contents', { path: input.path }),

        /** Uses Tauri dialog plugin directly from JS */
        selectExecutableFile: async (): Promise<string | null> => {
            const result = await open({
                filters: [
                    { name: 'Executable Files', extensions: ['exe'] },
                    { name: 'All Files', extensions: ['*'] },
                ],
            });
            return typeof result === 'string' ? result : null;
        },
    },

    backendHttp: {
        fetch: (input: FetchOptions) =>
            invoke<FetchResponse>('proxy_fetch', { options: input }),
    },

    telemetry: {
        getEnabled: () => invoke<boolean>('get_telemetry_enabled'),

        setEnabled: (input: { enabled: boolean }) =>
            invoke<boolean>('set_telemetry_enabled', { enabled: input.enabled }),
    },

    app: {
        getVersion: () => invoke<string>('get_app_version'),

        checkForUpdate: () => invoke<{
            available: boolean;
            version?: string;
            currentVersion?: string;
            error?: string;
            reason?: string;
        }>('check_for_update'),

        downloadUpdate: () => invoke<boolean>('download_update'),

        installUpdate: () => invoke<void>('install_update'),
    },

    assets: {
        getLogoBase64: () =>
            invoke<string | null>('get_logo_base64'),

        getLogoPngPath: () => invoke<string>('get_logo_png_path'),
    },
};

export type TauriClient = typeof tauriClient;
