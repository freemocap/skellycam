import { listen, type UnlistenFn } from '@tauri-apps/api/event';

// ── Auto-update events ────────────────────────────────────────

export function onUpdateAvailable(
    callback: (info: { version: string; currentVersion: string }) => void,
): UnlistenFn {
    const unlisten = listen<{ version: string; currentVersion: string }>(
        'update-available',
        (event) => callback(event.payload),
    );
    // Tauri listen() returns a Promise<UnlistenFn>, but we need sync return.
    // Wrap in an immediately-invoked async and store the cleanup.
    let cleanup: UnlistenFn = () => {};
    let cancelled = false;
    unlisten.then((fn) => {
        if (!cancelled) cleanup = fn;
        else fn();
    });
    return () => {
        cancelled = true;
        cleanup();
    };
}

export function onDownloadProgress(
    callback: (progress: {
        percent: number;
        bytesPerSecond: number;
        transferred: number;
        total: number;
    }) => void,
): UnlistenFn {
    const unlisten = listen<{
        percent: number;
        bytesPerSecond: number;
        transferred: number;
        total: number;
    }>('download-progress', (event) => callback(event.payload));
    let cleanup: UnlistenFn = () => {};
    let cancelled = false;
    unlisten.then((fn) => {
        if (!cancelled) cleanup = fn;
        else fn();
    });
    return () => {
        cancelled = true;
        cleanup();
    };
}

export function onUpdateDownloaded(
    callback: (info: { version: string }) => void,
): UnlistenFn {
    const unlisten = listen<{ version: string }>(
        'update-downloaded',
        (event) => callback(event.payload),
    );
    let cleanup: UnlistenFn = () => {};
    let cancelled = false;
    unlisten.then((fn) => {
        if (!cancelled) cleanup = fn;
        else fn();
    });
    return () => {
        cancelled = true;
        cleanup();
    };
}

export function onUpdateError(
    callback: (error: { message: string }) => void,
): UnlistenFn {
    const unlisten = listen<{ message: string }>(
        'update-error',
        (event) => callback(event.payload),
    );
    let cleanup: UnlistenFn = () => {};
    let cancelled = false;
    unlisten.then((fn) => {
        if (!cancelled) cleanup = fn;
        else fn();
    });
    return () => {
        cancelled = true;
        cleanup();
    };
}

// ── Menu events ───────────────────────────────────────────────

export function onMenuAction(
    callback: (action: string) => void,
): UnlistenFn {
    const unlisten = listen<string>('menu-action', (event) =>
        callback(event.payload),
    );
    let cleanup: UnlistenFn = () => {};
    let cancelled = false;
    unlisten.then((fn) => {
        if (!cancelled) cleanup = fn;
        else fn();
    });
    return () => {
        cancelled = true;
        cleanup();
    };
}
