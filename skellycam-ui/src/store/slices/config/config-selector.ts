import { RootState } from '../../types';

export const selectServerConfig = (state: RootState) => state.config.server;

export const selectServerUrl = (state: RootState) => {
    const { host, port } = state.config.server;
    return `http://${host}:${port}`;
};

export const selectWebSocketUrl = (state: RootState) => {
    const { host, port } = state.config.server;
    return `ws://${host}:${port}/skellycam/websocket/connect`;
};

// Selector that returns all endpoints
export const selectEndpoints = (state: RootState) => {
    const base = selectServerUrl(state);
    return {
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
    };
};
