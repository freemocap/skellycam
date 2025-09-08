import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import {
    ServerConfig,
    ServerState,
    ServerStatus,
    WebSocketStatus
} from './server-types';
import { checkServerHealth, startServer, stopServer } from './server-thunks';

// Helper to load config from localStorage
const loadConfigFromStorage = (): ServerConfig => ({
    host: localStorage.getItem('server-host') || 'localhost',
    port: parseInt(localStorage.getItem('server-port') || '8006'),
    autoConnect: localStorage.getItem('auto-connect') === 'true',
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
        localStorage.setItem('auto-connect', config.autoConnect.toString());
    }
};

const initialState: ServerState = {
    // Load config from localStorage
    config: loadConfigFromStorage(),

    // Server process state
    status: 'not-connected',
    errorMessage: null,
    retryCount: 0,
    lastHealthCheck: null,
    processInfo: {
        pid: null,
        executablePath: null,
    },

    // WebSocket state
    websocket: {
        status: 'disconnected',
        error: null,
        reconnectAttempts: 0,
        lastConnectedAt: null,
        lastDisconnectedAt: null,
    },
};

export const serverSlice = createSlice({
    name: 'server',
    initialState,
    reducers: {
        // Config actions
        updateServerConfig: (state, action: PayloadAction<Partial<ServerConfig>>) => {
            state.config = { ...state.config, ...action.payload };
            saveConfigToStorage(action.payload);
        },

        // Server process actions
        serverStatusUpdated: (state, action: PayloadAction<ServerStatus>) => {
            state.status = action.payload;
        },
        serverErrorSet: (state, action: PayloadAction<string | null>) => {
            state.errorMessage = action.payload;
        },
        retryCountUpdated: (state, action: PayloadAction<number>) => {
            state.retryCount = action.payload;
        },
        healthCheckRecorded: (state) => {
            state.lastHealthCheck = new Date().toISOString();
        },
        processInfoUpdated: (
            state,
            action: PayloadAction<Partial<ServerState['processInfo']>>
        ) => {
            state.processInfo = { ...state.processInfo, ...action.payload };
        },

        // WebSocket actions
        websocketConnecting: (state) => {
            state.websocket.status = 'connecting';
            state.websocket.error = null;
        },
        websocketConnected: (state) => {
            state.websocket.status = 'connected';
            state.websocket.error = null;
            state.websocket.reconnectAttempts = 0;
            state.websocket.lastConnectedAt = new Date().toISOString();
        },
        websocketDisconnected: (state) => {
            state.websocket.status = 'disconnected';
            state.websocket.lastDisconnectedAt = new Date().toISOString();
        },
        websocketReconnecting: (state, action: PayloadAction<number>) => {
            state.websocket.status = 'reconnecting';
            state.websocket.reconnectAttempts = action.payload;
        },
        websocketError: (state, action: PayloadAction<string>) => {
            state.websocket.status = 'error';
            state.websocket.error = action.payload;
        },
    },
    extraReducers: (builder) => {
        builder
            // Start server
            .addCase(startServer.pending, (state) => {
                state.status = 'spawning';
                state.errorMessage = null;
                state.retryCount = 0;
            })
            .addCase(startServer.fulfilled, (state, action) => {
                state.status = 'alive';
                state.errorMessage = null;
                state.processInfo = action.payload;
            })
            .addCase(startServer.rejected, (state, action) => {
                state.status = 'error';
                state.errorMessage = action.error.message || 'Failed to start server';
            })
            // Stop server
            .addCase(stopServer.pending, (state) => {
                state.status = 'shutting-down';
                state.errorMessage = null;
                // Also disconnect WebSocket
                state.websocket.status = 'disconnected';
            })
            .addCase(stopServer.fulfilled, (state) => {
                state.status = 'not-connected';
                state.processInfo = { pid: null, executablePath: null };
                // Ensure WebSocket is marked as disconnected
                state.websocket.status = 'disconnected';
                state.websocket.lastDisconnectedAt = new Date().toISOString();
            })
            .addCase(stopServer.rejected, (state, action) => {
                state.status = 'error';
                state.errorMessage = action.error.message || 'Failed to stop server';
            })
            // Health check
            .addCase(checkServerHealth.fulfilled, (state, action) => {
                state.status = action.payload ? 'alive' : 'not-connected';
                state.lastHealthCheck = new Date().toISOString();
            });
    },
});

export const {
    updateServerConfig,
    serverStatusUpdated,
    serverErrorSet,
    retryCountUpdated,
    healthCheckRecorded,
    processInfoUpdated,
    websocketConnecting,
    websocketConnected,
    websocketDisconnected,
    websocketReconnecting,
    websocketError,
} = serverSlice.actions;
