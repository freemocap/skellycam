import {serverApi, urlService} from "@/services/api";
import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState} from "@/store/types";
import {electronAPI} from "@/hooks/electron-service/electron-api";
import {retryCountUpdated} from "@/store/slices/server/server-slice";


const MAX_RETRIES = 10;
const RETRY_DELAY = 1000;

export const checkServerHealth = createAsyncThunk<boolean>(
    'server/checkHealth',
    async () => {
        try {
            const response = await fetch(urlService.endpoints.health, {
                signal: AbortSignal.timeout(3000),
            });
            return response.ok;
        } catch {
            return false;
        }
    }
);

export const startServer = createAsyncThunk<
    { pid: number | null; executablePath: string | null },
    { exePath?: string | null } | undefined,
    { state: RootState }
>('server/start', async (args, { dispatch, getState }) => {
    if (!electronAPI) {
        throw new Error('Electron API not available');
    }

    // Shutdown any existing server first
    try {
        await serverApi.shutdown();
        await new Promise((resolve) => setTimeout(resolve, 500));
    } catch {
        // Ignore shutdown errors
    }

    // Start the server
    let executablePath = args?.exePath;

    if (!executablePath) {
        // Try to find a valid executable
        const currentPath = await electronAPI.pythonServer.getExecutablePath.query();
        if (currentPath) {
            executablePath = currentPath;
        } else {
            const candidates = await electronAPI.pythonServer.getExecutableCandidates.query();
            const validCandidate = candidates.find((c: any) => c.isValid);
            if (validCandidate) {
                executablePath = validCandidate.path;
            }
        }
    }

    await electronAPI.pythonServer.start.mutate({ exePath: executablePath });

    // Wait for server to be ready with retries
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        dispatch(retryCountUpdated(attempt));
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY));

        const isHealthy = await dispatch(checkServerHealth()).unwrap();
        if (isHealthy) {
            const processInfo = await electronAPI.pythonServer.getProcessInfo.query();
            return {
                pid: processInfo?.pid || null,
                executablePath,
            };
        }
    }

    throw new Error(`Server failed to start after ${MAX_RETRIES} attempts`);
});

export const stopServer = createAsyncThunk<void>(
    'server/stop',
    async () => {
        // Try graceful shutdown first
        try {
            await serverApi.shutdown();
            await new Promise((resolve) => setTimeout(resolve, 500));
        } catch {
            // Continue with force stop if graceful fails
        }

        // Force stop via IPC
        if (electronAPI) {
            await electronAPI.pythonServer.stop.mutate();
        }
    }
);

export const refreshExecutableCandidates = createAsyncThunk(
    'server/refreshCandidates',
    async () => {
        if (!electronAPI) {
            throw new Error('Electron API not available');
        }
        return electronAPI.pythonServer.refreshCandidates.mutate();
    }
);
