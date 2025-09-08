import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store/types";
import {electronIpc} from "@/services/electron-ipc/electron-ipc";
import {retryCountUpdated} from "@/store/slices/server/server-slice";
import {selectEndpoints} from "@/store";


const MAX_RETRIES = 10;
const RETRY_DELAY = 1000;


export const checkServerHealth = createAsyncThunk<
    boolean,
    void,
    { state: RootState }
>('server/checkHealth', async (_, { getState }) => {
    const state = getState();
    const endpoints = selectEndpoints(state);

    try {
        const response = await fetch(endpoints.health, {
            signal: AbortSignal.timeout(3000),
        });
        return response.ok;
    } catch {
        return false;
    }
});

export const startServer = createAsyncThunk<
    { pid: number | null; executablePath: string | null },
    { exePath?: string | null } | undefined,
    { state: RootState }
>('server/start', async (args, { dispatch, getState }) => {
    if (!electronIpc) {
        throw new Error('Electron API not available');
    }

    const state = getState();
    const endpoints = selectEndpoints(state);

    // Shutdown any existing server first
    try {
        await fetch(endpoints.shutdown, { method: 'POST' });
        await new Promise((resolve) => setTimeout(resolve, 500));
    } catch {
        // Ignore shutdown errors
    }

    // Start the server
    let executablePath: string | null = args?.exePath ?? null;

    if (!executablePath) {
        // Try to find a valid executable
        const currentPath = await electronIpc.pythonServer.getExecutablePath.query();
        if (currentPath) {
            executablePath = currentPath;
        } else {
            const candidates = await electronIpc.pythonServer.getExecutableCandidates.query();
            const validCandidate = candidates.find((c: any) => c.isValid);
            if (validCandidate) {
                executablePath = validCandidate.path;
            }
        }
    }

    await electronIpc.pythonServer.start.mutate({ exePath: executablePath });

    // Wait for server to be ready with retries
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        dispatch(retryCountUpdated(attempt));
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY));

        const isHealthy = await dispatch(checkServerHealth()).unwrap();
        if (isHealthy) {
            const processInfo = await electronIpc.pythonServer.getProcessInfo.query();
            return {
                pid: processInfo?.pid || null,
                executablePath,
            };
        }
    }

    throw new Error(`Server failed to start after ${MAX_RETRIES} attempts`);
});

export const stopServer = createAsyncThunk<
    void,
    void,
    { state: RootState }
>('server/stop', async (_, { getState }) => {
    const state = getState();
    const endpoints = selectEndpoints(state);

    // Try graceful shutdown first
    try {
        await fetch(endpoints.shutdown, { method: 'POST' });
        await new Promise((resolve) => setTimeout(resolve, 500));
    } catch {
        // Continue with force stop if graceful fails
    }

    // Force stop via IPC
    if (electronIpc) {
        await electronIpc.pythonServer.stop.mutate();
    }
});

export const refreshExecutableCandidates = createAsyncThunk(
    'server/refreshCandidates',
    async () => {
        if (!electronIpc) {
            throw new Error('Electron API not available');
        }
        return electronIpc.pythonServer.refreshCandidates.mutate();
    }
);
