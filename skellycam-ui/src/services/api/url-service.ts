import {store} from "@/store";

class UrlService {
    private static instance: UrlService;

    private constructor() {}

    static getInstance(): UrlService {
        if (!UrlService.instance) {
            UrlService.instance = new UrlService();
        }
        return UrlService.instance;
    }

    private get config() {
        // Get config from Redux store instead of maintaining separate state
        const state = store.getState();
        return state.server.config;
    }

    get baseHttpUrl(): string {
        return `http://${this.config.host}:${this.config.port}`;
    }

    get websocketUrl(): string {
        return `ws://${this.config.host}:${this.config.port}/skellycam/websocket/connect`;
    }

    get endpoints() {
        const base = this.baseHttpUrl;
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
        } as const;
    }
}

export const urlService = UrlService.getInstance();
