/**
 * backendFetch — drop-in replacement for fetch() when calling the Python backend.
 *
 * In Electron production builds the renderer loads from file://, making requests
 * to localhost:53117 cross-origin. Chromium's cross-origin connection pool fills up
 * with stalled requests and new ones never get a socket slot.
 *
 * This routes all backend HTTP calls through the Electron main process via IPC,
 * using net.fetch() which has no connection-pool or CORS restrictions.
 * Falls back to native fetch() in non-Electron contexts (plain browser).
 */
import { electronIpcClient } from '@/services/electron-ipc/electron-ipc-client';
import { tauriTrpcClient } from '@/services/tauri-ipc/tauri-trpc-shim';

interface BackendResponse {
    ok: boolean;
    status: number;
    statusText: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    json(): Promise<any>;
    text(): Promise<string>;
}

export async function backendFetch(url: string, init?: RequestInit): Promise<BackendResponse> {
    const method = (init?.method ?? 'GET').toUpperCase();
    const headers = init?.headers as Record<string, string> | undefined;
    const body = typeof init?.body === 'string' ? init.body : undefined;

    // Check at call time so we always reflect the actual runtime environment.
    if (typeof window !== 'undefined') {
        if ((window as any).__TAURI_INTERNALS__) {
            const result = await tauriTrpcClient.backendHttp.fetch.mutate({ url, method, headers, body });
            return {
                ok: result.ok,
                status: result.status,
                statusText: result.statusText,
                json: async () => JSON.parse(result.data),
                text: async () => result.data,
            };
        }
        if (window.electronAPI) {
            const result = await electronIpcClient.backendHttp.fetch.mutate({ url, method, headers, body });
            return {
                ok: result.ok,
                status: result.status,
                statusText: result.statusText,
                json: async () => JSON.parse(result.data),
                text: async () => result.data,
            };
        }
    }

    // Non-Electron/non-Tauri fallback (plain browser dev)
    return fetch(url, init);
}
