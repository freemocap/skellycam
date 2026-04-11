export const DEFAULT_HOST = 'localhost';
export const DEFAULT_PORT = 53117;
export const WS_PATH = '/ws';

class ServerUrls {
    private host: string = DEFAULT_HOST;
    private port: number = DEFAULT_PORT;

    getHost(): string {
        return this.host;
    }

    getPort(): number {
        return this.port;
    }

    setHost(host: string): void {
        this.host = host;
    }

    setPort(port: number): void {
        this.port = port;
    }

    getHttpUrl(): string {
        return `http://${this.host}:${this.port}`;
    }

    getWebSocketUrl(): string {
        return `ws://${this.host}:${this.port}${WS_PATH}`;
    }

    get endpoints() {
        const baseUrl = this.getHttpUrl();
        const cameraGroupsBase = `${baseUrl}/camera-groups`;

        return {
            // Server management
            health: `${baseUrl}/health`,
            shutdown: `${baseUrl}/shutdown`,

            // Device discovery
            detectCameras: `${baseUrl}/devices/cameras`,
            detectMicrophones: `${baseUrl}/devices/microphones`,

            // Camera groups — per-group
            cameraGroups: cameraGroupsBase,
            cameraGroup: (groupId: string) => `${cameraGroupsBase}/${encodeURIComponent(groupId)}`,
            cameraGroupRecording: (groupId: string) => `${cameraGroupsBase}/${encodeURIComponent(groupId)}/recording`,
            cameraGroupPause: (groupId: string) => `${cameraGroupsBase}/${encodeURIComponent(groupId)}/pause`,
            cameraGroupUnpause: (groupId: string) => `${cameraGroupsBase}/${encodeURIComponent(groupId)}/unpause`,

            // Camera groups — bulk /all/ shortcuts
            allCameraGroups: `${cameraGroupsBase}/all`,
            allCameraGroupsRecording: `${cameraGroupsBase}/all/recording`,
            allCameraGroupsPause: `${cameraGroupsBase}/all/pause`,
            allCameraGroupsUnpause: `${cameraGroupsBase}/all/unpause`,

            // Recordings (file browsing / playback)
            recordings: `${baseUrl}/recordings`,
            recording: (recordingId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}`,
            recordingVideos: (recordingId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}/videos`,
            recordingVideoStream: (recordingId: string, videoId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}/videos/${encodeURIComponent(videoId)}`,
            recordingAllTimestamps: (recordingId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}/timestamps`,
            recordingVideoTimestamps: (recordingId: string, videoId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}/videos/${encodeURIComponent(videoId)}/timestamps`,

            // WebSocket
            websocket: this.getWebSocketUrl(),

            // --- Legacy aliases ---
            /** @deprecated Use cameraGroup(id) */
            camerasConnectOrUpdate: `${cameraGroupsBase}/default`,
            /** @deprecated Use allCameraGroups (DELETE) */
            closeAll: `${cameraGroupsBase}/all`,
            /** @deprecated Use recordings */
            playbackRecordings: `${baseUrl}/recordings`,
            /** @deprecated Use recordingVideos() */
            playbackVideos: (recordingId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}/videos`,
            /** @deprecated Use recordingVideoStream() */
            playbackVideoStream: (recordingId: string, videoId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}/videos/${encodeURIComponent(videoId)}`,
            /** @deprecated Use recordingAllTimestamps() */
            playbackAllTimestamps: (recordingId: string) =>
                `${baseUrl}/recordings/${encodeURIComponent(recordingId)}/timestamps`,
        };
    }
}

// Export singleton instance
export const serverUrls = new ServerUrls();
