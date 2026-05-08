/**
 * Compatibility shim: wraps the Tauri client to match the tRPC-style API shape
 * (`.mutate()` / `.query()` methods) so existing React components don't need
 * to change their call patterns.
 */
import { tauriClient } from './tauri-client';

// Wrap each method in a { mutate } or { query } object to match tRPC convention.
// For Tauri, the distinction doesn't matter — both call invoke().

function mutate<T extends (...args: any[]) => any>(fn: T) {
    return { mutate: fn };
}

function query<T extends (...args: any[]) => any>(fn: T) {
    return { query: fn };
}

export const tauriTrpcClient = {
    pythonServer: {
        start: mutate(tauriClient.pythonServer.start),
        stop: mutate(tauriClient.pythonServer.stop),
        getExecutablePath: query(tauriClient.pythonServer.getExecutablePath),
        getExecutableCandidates: query(tauriClient.pythonServer.getExecutableCandidates),
        refreshCandidates: mutate(tauriClient.pythonServer.refreshCandidates),
        isRunning: query(tauriClient.pythonServer.isRunning),
        getProcessInfo: query(tauriClient.pythonServer.getProcessInfo),
    },
    fileSystem: {
        selectDirectory: mutate(tauriClient.fileSystem.selectDirectory),
        openFolder: mutate(tauriClient.fileSystem.openFolder),
        getHomeDirectory: query(tauriClient.fileSystem.getHomeDirectory),
        getFolderContents: query(tauriClient.fileSystem.getFolderContents),
        selectExecutableFile: mutate(tauriClient.fileSystem.selectExecutableFile),
    },
    backendHttp: {
        fetch: mutate(tauriClient.backendHttp.fetch),
    },
    telemetry: {
        getEnabled: query(tauriClient.telemetry.getEnabled),
        setEnabled: mutate(tauriClient.telemetry.setEnabled),
    },
    app: {
        getVersion: query(tauriClient.app.getVersion),
        checkForUpdate: mutate(tauriClient.app.checkForUpdate),
        downloadUpdate: mutate(tauriClient.app.downloadUpdate),
        installUpdate: mutate(tauriClient.app.installUpdate),
    },
    assets: {
        getLogoBase64: query(tauriClient.assets.getLogoBase64),
        getLogoPngPath: query(tauriClient.assets.getLogoPngPath),
    },
};
