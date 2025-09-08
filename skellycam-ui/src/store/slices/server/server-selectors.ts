import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';

// Config selectors
export const selectServerConfig = (state: RootState) => state.server.config;
export const selectServerHost = (state: RootState) => state.server.config.host;
export const selectServerPort = (state: RootState) => state.server.config.port;
export const selectServerAutoConnect = (state: RootState) => state.server.config.autoConnect;

// Server process selectors
export const selectServerStatus = (state: RootState) => state.server.status;
export const selectServerError = (state: RootState) => state.server.errorMessage;
export const selectServerProcessInfo = (state: RootState) => state.server.processInfo;

// WebSocket selectors
export const selectWebSocketStatus = (state: RootState) => state.server.websocket.status;
export const selectWebSocketError = (state: RootState) => state.server.websocket.error;
export const selectWebSocketReconnectAttempts = (state: RootState) =>
    state.server.websocket.reconnectAttempts;

// Computed selectors
export const selectIsServerAlive = createSelector(
    [selectServerStatus],
    (status) => status === 'alive'
);

export const selectIsServerTransitioning = createSelector(
    [selectServerStatus],
    (status) => status === 'spawning' || status === 'shutting-down'
);

export const selectIsWebSocketConnected = createSelector(
    [selectWebSocketStatus],
    (status) => status === 'connected'
);

export const selectIsWebSocketConnecting = createSelector(
    [selectWebSocketStatus],
    (status) => status === 'connecting' || status === 'reconnecting'
);

// URL selectors
export const selectBaseHttpUrl = createSelector(
    [selectServerHost, selectServerPort],
    (host, port) => `http://${host}:${port}`
);

export const selectWebSocketUrl = createSelector(
    [selectServerHost, selectServerPort],
    (host, port) => `ws://${host}:${port}/skellycam/websocket/connect`
);

export const selectServerUrls = createSelector(
    [selectBaseHttpUrl, selectWebSocketUrl],
    (httpUrl, wsUrl) => ({
        http: httpUrl,
        websocket: wsUrl,
    })
);

export const selectEndpoints = createSelector(
    [selectBaseHttpUrl],
    (base) => ({
        // Server endpoints
        health: `${base}/health`,
        shutdown: `${base}/shutdown`,

        // Camera endpoints
        detectCameras: `${base}/skellycam/camera/detect`,
        createGroup: `${base}/skellycam/camera/group/apply`,
        closeAll: `${base}/skellycam/camera/group/close/all`,
        updateConfigs: `${base}/skellycam/camera/update`,
        pauseUnpauseCameras: `${base}/skellycam/camera/group/all/pause_unpause`,

        // Recording endpoints
        startRecording: `${base}/skellycam/camera/group/all/record/start`,
        stopRecording: `${base}/skellycam/camera/group/all/record/stop`,
    })
);
