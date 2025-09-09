// store/slices/server/server-thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import { RootState } from '@/store/types';
import { electronIpc } from '@/services/electron-ipc/electron-ipc';
import {
    ServerStartupResult,
    ExternalServerConnectionResult,
    ExecutableCandidate
} from './server-types';
import { connectionStatusChanged, healthCheckCompleted } from './server-slice';

const MAX_HEALTH_CHECK_RETRIES = 10;
const HEALTH_CHECK_DELAY = 1000;

/**
 * Build server URL from host and port
 */
const buildServerUrl = (host: string, port: number): string => {
    return `http://${host}:${port}`;
};

/**
 * Check if a server is healthy at the given URL
 */
const checkHealthAtUrl = async (url: string): Promise<boolean> => {
    try {
        const response = await fetch(`${url}/health`, {
            signal: AbortSignal.timeout(3000),
        });
        return response.ok;
    } catch {
        return false;
    }
};

/**
 * Wait for server to become healthy with retries
 */
const waitForServerHealth = async (
    url: string,
    maxRetries: number = MAX_HEALTH_CHECK_RETRIES,
    delay: number = HEALTH_CHECK_DELAY
): Promise<boolean> => {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        const isHealthy = await checkHealthAtUrl(url);
        if (isHealthy) {
            return true;
        }

        if (attempt < maxRetries) {
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    return false;
};

/**
 * Start a managed server (spawned by this app)
 * Only available in Electron environment
 */
export const startManagedServer = createAsyncThunk<
    ServerStartupResult,
    { executablePath?: string | null } | undefined,
    { state: RootState }
>(
    'server/startManaged',
    async (args, { getState, dispatch }) => {
        if (!electronIpc) {
            throw new Error('Cannot spawn server - not running in Electron');
        }

        const state = getState();
        const { host, port, preferredExecutablePath } = state.server.config;
        const serverUrl = buildServerUrl(host, port);

        // Determine which executable to use
        let executablePath = args?.executablePath ?? preferredExecutablePath;

        if (!executablePath) {
            // Try to find a valid executable
            const candidates = await electronIpc.pythonServer.getExecutableCandidates.query();
            const validCandidate = candidates.find((c: ExecutableCandidate) => c.isValid);

            if (!validCandidate) {
                throw new Error('No valid Python server executable found');
            }

            executablePath = validCandidate.path;
        }

        // First, try to gracefully shutdown any existing server at this address
        try {
            await fetch(`${serverUrl}/shutdown`, {
                method: 'POST',
                signal: AbortSignal.timeout(1000)
            });
            await new Promise(resolve => setTimeout(resolve, 500));
        } catch {
            // Ignore shutdown errors - server might not be running
        }

        // Spawn the new server process
        await electronIpc.pythonServer.start.mutate({ exePath: executablePath });

        // Wait for server to become healthy
        dispatch(connectionStatusChanged('connecting'));
        const isHealthy = await waitForServerHealth(serverUrl);

        if (!isHealthy) {
            // Kill the process if it didn't become healthy
            await electronIpc.pythonServer.stop.mutate();
            throw new Error(`Server failed to start after ${MAX_HEALTH_CHECK_RETRIES} attempts`);
        }

        // Get process info
        const processInfo = await electronIpc.pythonServer.getProcessInfo.query();

        dispatch(healthCheckCompleted(true));

        return {
            process: {
                pid: processInfo?.pid || null,
                executablePath,
            },
            serverUrl,
        };
    }
);

/**
 * Stop the managed server
 * Only available in Electron environment
 */
export const stopManagedServer = createAsyncThunk<
    void,
    void,
    { state: RootState }
>(
    'server/stopManaged',
    async (_, { getState }) => {
        if (!electronIpc) {
            throw new Error('Cannot stop server - not running in Electron');
        }

        const state = getState();
        const serverUrl = state.server.connection.serverUrl;

        // Try graceful shutdown first
        if (serverUrl) {
            try {
                await fetch(`${serverUrl}/shutdown`, {
                    method: 'POST',
                    signal: AbortSignal.timeout(1000)
                });
                await new Promise(resolve => setTimeout(resolve, 500));
            } catch {
                // Continue with force stop if graceful fails
            }
        }

        // Force stop via IPC
        await electronIpc.pythonServer.stop.mutate();
    }
);

/**
 * Connect to an external server (not managed by this app)
 */
export const connectToExternalServer = createAsyncThunk<
    ExternalServerConnectionResult,
    { host?: string; port?: number } | undefined,
    { state: RootState }
>(
    'server/connectExternal',
    async (args, { getState, dispatch }) => {
        const state = getState();
        const host = args?.host ?? state.server.config.host;
        const port = args?.port ?? state.server.config.port;
        const serverUrl = buildServerUrl(host, port);

        dispatch(connectionStatusChanged('connecting'));

        // Check if server is healthy
        const isHealthy = await checkHealthAtUrl(serverUrl);

        if (!isHealthy) {
            throw new Error(`No server responding at ${serverUrl}`);
        }

        dispatch(healthCheckCompleted(true));

        return {
            serverUrl,
            isHealthy,
        };
    }
);

/**
 * Disconnect from any server (managed or external)
 */
export const disconnectFromServer = createAsyncThunk<
    void,
    void,
    { state: RootState }
>(
    'server/disconnect',
    async (_, { getState, dispatch }) => {
        const state = getState();
        const { mode, managedProcess } = state.server.connection;

        // If it's a managed server, stop the process
        if (mode === 'managed' && managedProcess && electronIpc) {
            await dispatch(stopManagedServer()).unwrap();
        }

        // For external servers, just update the state
        // The reducer will handle clearing the connection
    }
);

/**
 * Check server health
 */
export const checkServerHealth = createAsyncThunk<
    boolean,
    void,
    { state: RootState }
>(
    'server/checkHealth',
    async (_, { getState }) => {
        const state = getState();
        const serverUrl = state.server.connection.serverUrl;

        if (!serverUrl) {
            return false;
        }

        return await checkHealthAtUrl(serverUrl);
    }
);

/**
 * Refresh executable candidates
 * Only available in Electron environment
 */
export const refreshExecutableCandidates = createAsyncThunk<
    ExecutableCandidate[],
    void,
    { state: RootState }
>(
    'server/refreshCandidates',
    async (_, { dispatch }) => {
        if (!electronIpc) {
            return [];
        }

        const candidates = await electronIpc.pythonServer.refreshCandidates.mutate();
        return candidates;
    }
);

/**
 * Auto-connect to server based on configuration
 */
export const autoConnectToServer = createAsyncThunk<
    void,
    void,
    { state: RootState }
>(
    'server/autoConnect',
    async (_, { getState, dispatch }) => {
        const state = getState();
        const { autoSpawn, autoConnect } = state.server.config;

        // If already connected, nothing to do
        if (state.server.connection.status === 'connected') {
            return;
        }

        // Try to connect to existing server first
        if (autoConnect) {
            try {
                await dispatch(connectToExternalServer()).unwrap();
                return;
            } catch {
                // Server not available, continue to spawning if configured
            }
        }

        // If auto-spawn is enabled and we're in Electron, spawn a new server
        if (autoSpawn && electronIpc) {
            await dispatch(startManagedServer()).unwrap();
        }
    }
);
