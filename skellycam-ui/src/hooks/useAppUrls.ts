export interface DefaultUrlConfig {
    host: string;
    port: number;
}

// Default URL configuration
const defaultUrlConfig: DefaultUrlConfig = {
    host: 'localhost',
    port: 8006,
};


// Get the base HTTP URL
const getBaseHttpUrl = () => {
    const {host, port} = defaultUrlConfig;
    return `http://${host}:${port}`;
};

// Get a specific API URL
const getApiUrl = (path: string) => {
    return `${getBaseHttpUrl()}${path}`;
};

// Get WebSocket URL
const getWebSocketUrl = () => {
    const {host, port} = defaultUrlConfig;
    return `ws://${host}:${port}/ws`;
};

// Get all HTTP endpoint URLs
const getHttpEndpointUrls = () => {
    return {
        health: getApiUrl('/health'),
        shutdown: getApiUrl('/shutdown'),
        detectCameras: getApiUrl('/devices/cameras'),
        detectMicrophones: getApiUrl('/devices/microphones'),
        cameraGroup: getApiUrl('/camera-group'),
        recordings: getApiUrl('/recordings'),
    };
};

export const useAppUrls = {
    getBaseHttpUrl,
    getApiUrl,
    getWebSocketUrl,
    getHttpEndpointUrls,
};
