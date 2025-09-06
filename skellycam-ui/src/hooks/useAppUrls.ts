import { useServerConfig } from './useServerConfig';

// Export a hook version for React components
export const useAppUrls = () => {
    const { config, getBaseHttpUrl, getApiUrl, getWebSocketUrl, getHttpEndpointUrls } = useServerConfig();

    return {
        config,
        getBaseHttpUrl,
        getApiUrl,
        getWebSocketUrl,
        getHttpEndpointUrls,
    };
};

// For non-React contexts (like thunks), we need a singleton instance
// This will use the values from localStorage or defaults
class AppUrlsService {
    private host: string = 'localhost';
    private port: number = 8006;

    constructor() {
        this.loadConfig();
    }

    private loadConfig() {
        try {
            const stored = localStorage.getItem('skellycam-server-config');
            if (stored) {
                const config = JSON.parse(stored);
                this.host = config.host || 'localhost';
                this.port = config.port || 8006;
            }
        } catch (error) {
            console.error('Failed to load server config:', error);
        }
    }

    getBaseHttpUrl = () => {
        return `http://${this.host}:${this.port}`;
    };

    getApiUrl = (path: string) => {
        return `${this.getBaseHttpUrl()}${path}`;
    };

    getWebSocketUrl = () => {
        return `ws://${this.host}:${this.port}/skellycam/websocket/connect`;
    };

    getHttpEndpointUrls = () => {
        return {
            health: this.getApiUrl('/health'),
            shutdown: this.getApiUrl('/shutdown'),
            detectCameras: this.getApiUrl('/skellycam/camera/detect'),
            createGroup: this.getApiUrl('/skellycam/camera/group/apply'),
            closeAll: this.getApiUrl('/skellycam/camera/group/close/all'),
            updateConfigs: this.getApiUrl('/skellycam/camera/update'),
            startRecording: this.getApiUrl('/skellycam/camera/group/all/record/start'),
            stopRecording: this.getApiUrl('/skellycam/camera/group/all/record/stop'),
            pauseUnpauseCameras: this.getApiUrl('/skellycam/camera/group/all/pause_unpause'),
        };
    };

    // Allow manual refresh of config
    refreshConfig() {
        this.loadConfig();
    }
}

// Export singleton for non-React contexts
export const appUrlsService = new AppUrlsService();

