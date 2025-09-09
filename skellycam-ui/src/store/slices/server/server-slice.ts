import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import {
    ServerConfig,
    ServerState,
    ServerStatus,
    WebSocketStatus,
    ServerConnectionMode,
    ServerConnectionInfo
} from './server-types';
import {
    checkServerHealth,
    startManagedServer,
    stopManagedServer,
    connectToExternalServer,
    disconnectFromServer
} from './server-thunks';

// Helper to load config from localStorage
const loadConfigFromStorage = (): ServerConfig => ({
    host: localStorage.getItem('server-host') || 'localhost',
    port: parseInt(localStorage.getItem('server-port') || '8006'),
    autoConnect: localStorage.getItem('server-auto-connect') === 'true',
    autoSpawn: localStorage.getItem('server-auto-spawn') === 'true',
    preferredExecutablePath: localStorage.getItem('server-executable-path') || null,
});

// Helper to save config to localStorage
const saveConfigToStorage = (config: Partial<ServerConfig>): void => {
    if (config.host !== undefined) {
        localStorage.setItem('server-host', config.host);
    }
    if (config.port !== undefined) {
        localStorage.setItem('server-port', config.port.toString());
    }
    if (config.autoConnect !== undefined) {
        localStorage.setItem('server-auto-connect', config.autoConnect.toString());
    }
    if (config.autoSpawn !== undefined) {
        localStorage.setItem('server-auto-spawn', config.autoSpawn.toString());
    }
    if (config.preferredExecutablePath !== undefined) {
        localStorage.setItem('server-executable-path', config.preferredExecutablePath || '');
    }
};

const initialState: ServerState = {
    // Configuration
    config: loadConfigFromStorage(),

    // Connection info
    connection: {
        mode: 'none',
        status: 'disconnected',
        managedProcess: null,
        serverUrl: null,
        error: null,
        lastHealthCheck: null,
        retryCount: 0,
    },

    // WebSocket state
    websocket: {
        status: 'disconnected',
        error: null,
        reconnectAttempts: 0,
        lastConnectedAt: null,
        lastDisconnectedAt: null,
    },

    // Executable management (Electron only)
    executables: {
        candidates: [],
        lastRefresh: null,
        isRefreshing: false,
    }
};

export const serverSlice = createSlice({
    name: 'server',
    initialState,
    reducers: {
        // Configuration
        updateServerConfig: (state, action: PayloadAction<Partial<ServerConfig>>) => {
            state.config = { ...state.config, ...action.payload };
            saveConfigToStorage(action.payload);
        },

        // Connection management
        connectionModeChanged: (state, action: PayloadAction<ServerConnectionMode>) => {
            state.connection.mode = action.payload;
        },

        connectionStatusChanged: (state, action: PayloadAction<ServerStatus>) => {
            state.connection.status = action.payload;
        },

        connectionErrorSet: (state, action: PayloadAction<string | null>) => {
            state.connection.error = action.payload;
        },

        managedProcessUpdated: (state, action: PayloadAction<{
            pid: number | null;
            executablePath: string | null;
        } | null>) => {
            state.connection.managedProcess = action.payload;
        },

        serverUrlUpdated: (state, action: PayloadAction<string | null>) => {
            state.connection.serverUrl = action.payload;
        },

        healthCheckCompleted: (state, action: PayloadAction<boolean>) => {
            state.connection.lastHealthCheck = new Date().toISOString();
            if (action.payload && state.connection.status !== 'connected') {
                state.connection.status = 'connected';
            }
        },

        // WebSocket management
        websocketStatusChanged: (state, action: PayloadAction<WebSocketStatus>) => {
            state.websocket.status = action.payload;

            if (action.payload === 'connected') {
                state.websocket.error = null;
                state.websocket.reconnectAttempts = 0;
                state.websocket.lastConnectedAt = new Date().toISOString();
            } else if (action.payload === 'disconnected') {
                state.websocket.lastDisconnectedAt = new Date().toISOString();
            }
        },

        websocketErrorSet: (state, action: PayloadAction<string | null>) => {
            state.websocket.error = action.payload;
            if (action.payload) {
                state.websocket.status = 'error';
            }
        },

        websocketReconnectAttempt: (state) => {
            state.websocket.reconnectAttempts += 1;
            state.websocket.status = 'reconnecting';
        },

        // Executable management
        executablesUpdated: (state, action: PayloadAction<any[]>) => {
            state.executables.candidates = action.payload;
            state.executables.lastRefresh = new Date().toISOString();
            state.executables.isRefreshing = false;
        },

        executablesRefreshing: (state) => {
            state.executables.isRefreshing = true;
        },
    },

    extraReducers: (builder) => {
        builder
            // Start managed server
            .addCase(startManagedServer.pending, (state) => {
                state.connection.mode = 'managed';
                state.connection.status = 'connecting';
                state.connection.error = null;
                state.connection.retryCount = 0;
            })
            .addCase(startManagedServer.fulfilled, (state, action) => {
                state.connection.mode = 'managed';
                state.connection.status = 'connected';
                state.connection.managedProcess = action.payload.process;
                state.connection.serverUrl = action.payload.serverUrl;
                state.connection.error = null;
            })
            .addCase(startManagedServer.rejected, (state, action) => {
                state.connection.status = 'error';
                state.connection.error = action.error.message || 'Failed to start server';
                state.connection.mode = 'none';
            })

            // Stop managed server
            .addCase(stopManagedServer.pending, (state) => {
                state.connection.status = 'disconnecting';
            })
            .addCase(stopManagedServer.fulfilled, (state) => {
                state.connection.mode = 'none';
                state.connection.status = 'disconnected';
                state.connection.managedProcess = null;
                state.connection.serverUrl = null;
                state.websocket.status = 'disconnected';
            })
            .addCase(stopManagedServer.rejected, (state, action) => {
                state.connection.error = action.error.message || 'Failed to stop server';
            })

            // Connect to external server
            .addCase(connectToExternalServer.pending, (state) => {
                state.connection.mode = 'external';
                state.connection.status = 'connecting';
                state.connection.error = null;
            })
            .addCase(connectToExternalServer.fulfilled, (state, action) => {
                state.connection.mode = 'external';
                state.connection.status = 'connected';
                state.connection.serverUrl = action.payload.serverUrl;
                state.connection.error = null;
            })
            .addCase(connectToExternalServer.rejected, (state, action) => {
                state.connection.status = 'error';
                state.connection.error = action.error.message || 'Failed to connect to server';
                state.connection.mode = 'none';
            })

            // Disconnect from server
            .addCase(disconnectFromServer.fulfilled, (state) => {
                state.connection.mode = 'none';
                state.connection.status = 'disconnected';
                state.connection.serverUrl = null;
                state.websocket.status = 'disconnected';
            })

            // Health checks
            .addCase(checkServerHealth.fulfilled, (state, action) => {
                state.connection.lastHealthCheck = new Date().toISOString();
                if (action.payload) {
                    if (state.connection.status === 'connecting') {
                        state.connection.status = 'connected';
                    }
                } else if (state.connection.status === 'connected') {
                    state.connection.status = 'error';
                    state.connection.error = 'Server health check failed';
                }
            });
    },
});

export const {
    updateServerConfig,
    connectionModeChanged,
    connectionStatusChanged,
    connectionErrorSet,
    managedProcessUpdated,
    serverUrlUpdated,
    healthCheckCompleted,
    websocketStatusChanged,
    websocketErrorSet,
    websocketReconnectAttempt,
    executablesUpdated,
    executablesRefreshing,
} = serverSlice.actions;
