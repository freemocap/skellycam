// websocket-service.ts
// High-level service that orchestrates WebSocket operations and dispatches to appropriate stores

import { websocketManager } from './websocket-manager';
import { frameRouter } from '../frames/frame-router';

import {
    backendFramerateUpdated,
    frontendFramerateUpdated, logAdded, LogRecord, selectIsServerAlive,
    selectServerConfig,
    store,
    websocketConnecting
} from "@/store";
import {FramerateUpdateMessage, LogRecordMessage, WebSocketMessage} from "@/services/websocket/websocket-types";

class WebSocketService {
    private static instance: WebSocketService;
    private autoConnectEnabled = true;

    private constructor() {}

    static getInstance(): WebSocketService {
        if (!WebSocketService.instance) {
            WebSocketService.instance = new WebSocketService();
        }
        return WebSocketService.instance;
    }

    initialize(): void {
        // Initialize frame router
        frameRouter.initialize();

        // Setup message handlers
        this.setupMessageHandlers();

        // Monitor server status for auto-connect
        this.setupAutoConnect();
    }

    connect(): void {
        const state = store.getState();
        const config = selectServerConfig(state);
        const url = `ws://${config.host}:${config.port}/skellycam/websocket/connect`;

        store.dispatch(websocketConnecting());
        websocketManager.connect(url);
    }

    disconnect(): void {
        websocketManager.disconnect();
    }

    private setupMessageHandlers(): void {
        // Handle non-binary WebSocket messages
        websocketManager.addMessageHandler((message: WebSocketMessage) => {
            switch (message.message_type) {
                case 'framerate_update':
                    // Dispatch framerate updates to the framerate store
                    this.handleFramerateUpdate(message as FramerateUpdateMessage);
                    break;

                case 'log_record':
                    // Dispatch to log slice
                    this.handleLogRecord(message as LogRecordMessage);
                    break;

                default:
                    console.warn('Unknown message type:', message);
            }
        });
    }

    private handleFramerateUpdate(message: WebSocketMessage): void {
        if (message.message_type !== 'framerate_update') return;

        // Dispatch backend framerate update
        if (message.backend_framerate) {
            store.dispatch(backendFramerateUpdated(message.backend_framerate));
        }

        // Dispatch frontend framerate update
        if (message.frontend_framerate) {
            store.dispatch(frontendFramerateUpdated(message.frontend_framerate));
        }

        // Log for debugging if needed
        console.debug('Framerate update received:', {
            cameraGroupId: message.camera_group_id,
            backend: message.backend_framerate?.current,
            frontend: message.frontend_framerate?.current,
        });
    }

    private handleLogRecord(message: WebSocketMessage): void {
        if (message.message_type !== 'log_record') return;
        store.dispatch(logAdded(message as LogRecord));
    }

    private setupAutoConnect(): void {
        let lastServerStatus: boolean | null = null;

        store.subscribe(() => {
            if (!this.autoConnectEnabled) return;

            const state = store.getState();
            const isServerAlive = selectIsServerAlive(state);
            const isConnected = websocketManager.isConnected;

            // Auto-connect when server becomes alive
            if (isServerAlive && !isConnected && lastServerStatus !== isServerAlive) {
                this.connect();
            }

            lastServerStatus = isServerAlive;
        });
    }

    setAutoConnect(enabled: boolean): void {
        this.autoConnectEnabled = enabled;
    }
}

export const websocketService = WebSocketService.getInstance();
