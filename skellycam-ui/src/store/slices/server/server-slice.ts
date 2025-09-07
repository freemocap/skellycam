import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import {checkServerHealth, ServerConfig, ServerState, ServerStatus, startServer, stopServer} from "@/store";


const loadServerConfig = (): ServerConfig => {
    try {
        const stored = localStorage.getItem('skellycam-server-config');
        if (stored) {
            return {
                host: 'localhost',
                port: 8006,
                autoConnect: true,
                ...JSON.parse(stored)
            };
        }
    } catch (error) {
        console.error('Failed to load server config:', error);
    }
    return {
        host: 'localhost',
        port: 8006,
        autoConnect: true,
    };
};

const initialState: ServerState = {
    status: 'not-connected',
    errorMessage: null,
    retryCount: 0,
    lastHealthCheck: null,
    config: loadServerConfig(),
    processInfo: {
        pid: null,
        executablePath: null,
    },
};

export const serverSlice = createSlice({
    name: 'server',
    initialState,
    reducers: {
        serverStatusUpdated: (state, action: PayloadAction<ServerStatus>) => {
            state.status = action.payload;
        },
        serverConfigUpdated: (state, action: PayloadAction<Partial<ServerConfig>>) => {
            state.config = { ...state.config, ...action.payload };
            // Persist to localStorage
            localStorage.setItem('skellycam-server-config', JSON.stringify(state.config));
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
            })
            .addCase(stopServer.fulfilled, (state) => {
                state.status = 'not-connected';
                state.processInfo = { pid: null, executablePath: null };
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
    serverStatusUpdated,
    serverConfigUpdated,
    serverErrorSet,
    retryCountUpdated,
    healthCheckRecorded,
    processInfoUpdated,
} = serverSlice.actions;
