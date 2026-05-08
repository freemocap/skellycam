export { tauriClient, type TauriClient } from './tauri-client';
export { isTauri } from './tauri-detection';
export { useTauriIPC } from './use-tauri-ipc';
export {
    onUpdateAvailable,
    onDownloadProgress,
    onUpdateDownloaded,
    onUpdateError,
    onMenuAction,
} from './tauri-events';
export type {
    ExecutableCandidate,
    ProcessInfo,
    FolderEntry,
    FetchOptions,
    FetchResponse,
} from './tauri-types';
