// services/url/url-service.ts

/**
 * Simple stateless service for building server URLs
 */
class UrlService {
    private readonly host = 'localhost';
    private readonly port = 53117;

    /**
     * Get HTTP base URL
     */
    getHttpUrl(): string {
        return `http://${this.host}:${this.port}`;
    }

    /**
     * Get WebSocket base URL
     */
    getWebSocketUrl(): string {
        return `ws://${this.host}:${this.port}/skellycam/websocket/connect`;
    }
    get endpoints() {
        const baseUrl = this.getHttpUrl();

        return {
            // Server management
            health: `${baseUrl}/health`,
            shutdown: `${baseUrl}/shutdown`,

            // Camera endpoints
            detectCameras: `${baseUrl}/skellycam/camera/detect`,
            createGroup: `${baseUrl}/skellycam/camera/group/apply`,
            closeAll: `${baseUrl}/skellycam/camera/group/close/all`,
            updateConfigs: `${baseUrl}/skellycam/camera/update`,
            pauseUnpauseCameras: `${baseUrl}/skellycam/camera/group/all/pause_unpause`,

            // Recording endpoints
            startRecording: `${baseUrl}/skellycam/camera/group/all/record/start`,
            stopRecording: `${baseUrl}/skellycam/camera/group/all/record/stop`,

            // WebSocket
            websocket: this.getWebSocketUrl(),
        };
    }
}

// Export singleton instance
export const urlService = new UrlService();
