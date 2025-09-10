// services/websocket/websocket-service.ts
import { store } from '@/store';
import {
    websocketConnected,
    websocketDisconnected,
    websocketError,
    websocketReconnecting,
    backendFramerateUpdated,
    frontendFramerateUpdated,
    logAdded,
    selectServerConfig,
    selectIsServerAlive,
    type LogRecord
} from '@/store';
import { frameRouter } from '../frames/frame-router';
import type {
    WebSocketMessage,
    FramerateUpdateMessage,
    LogRecordMessage
} from './websocket-types';

export type MessageHandler = (data: WebSocketMessage) => void;
export type BinaryHandler = (data: ArrayBuffer) => void;

interface WebSocketConfig {
    reconnect: boolean;
    reconnectInterval: number;
    maxReconnectAttempts: number;
    autoConnect: boolean;
    healthCheckInterval: number;
}

class WebSocketService {
    private static instance: WebSocketService;
    private ws: WebSocket | null = null;
    private messageHandlers = new Set<MessageHandler>();
    private binaryHandlers = new Set<BinaryHandler>();
    private reconnectTimer: NodeJS.Timeout | null = null;
    private healthCheckTimer: NodeJS.Timeout | null = null;
    private reconnectAttempts: number = 0;
    private intentionalDisconnect: boolean = false; // Track if disconnect was intentional
    private config: WebSocketConfig = {
        reconnect: true,
        reconnectInterval: 1000,
        maxReconnectAttempts: 10,
        autoConnect: true,
        healthCheckInterval: 30000, // 30 seconds
    };
    private url: string | null = null;
    private isInitialized: boolean = false;
    private unsubscribe: (() => void) | null = null;

    private constructor() {}

    static getInstance(): WebSocketService {
        if (!WebSocketService.instance) {
            WebSocketService.instance = new WebSocketService();
        }
        return WebSocketService.instance;
    }

    /**
     * Initialize the service and set up auto-connect monitoring
     */
    initialize(): void {
        if (this.isInitialized) return;

        // Initialize frame router
        frameRouter.initialize();

        // Setup auto-connect monitoring
        this.setupAutoConnect();

        this.isInitialized = true;
    }

    /**
     * Connect to WebSocket server
     */
    connect(url?: string): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }

        // Reset flags when explicitly connecting
        this.intentionalDisconnect = false;
        this.config.reconnect = true;
        this.reconnectAttempts = 0;

        // Build URL if not provided
        if (!url) {
            const state = store.getState();
            const config = selectServerConfig(state);
            url = `ws://${config.host}:${config.port}/skellycam/websocket/connect`;
        }

        this.url = url;
        this.cleanup();

        try {
            console.log(`Connecting to WebSocket: ${url}`);
            this.ws = new WebSocket(url);
            this.ws.binaryType = 'arraybuffer';
            this.setupEventHandlers();
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Connection failed';
            console.error('WebSocket connection error:', errorMsg);
            store.dispatch(websocketError(errorMsg));
        }
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect(): void {
        console.log('Disconnecting WebSocket');
        this.intentionalDisconnect = true;
        this.config.reconnect = false;
        this.cleanup();
        store.dispatch(websocketDisconnected());
    }

    /**
     * Send data through WebSocket
     */
    send(data: string | ArrayBuffer): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(data);
        } else {
            console.warn('Cannot send - WebSocket not connected');
        }
    }

    /**
     * Send JSON message
     */
    sendMessage(message: object): void {
        this.send(JSON.stringify(message));
    }

    /**
     * Acknowledge frame rendered
     */
    acknowledgeFrameRendered(cameraId: string, frameNumber: number): void {
        this.sendMessage({
            type: 'frame_ack',
            camera_id: cameraId,
            frame_number: frameNumber,
        });
    }

    /**
     * Add custom message handler
     */
    addMessageHandler(handler: MessageHandler): () => void {
        this.messageHandlers.add(handler);
        return () => this.messageHandlers.delete(handler);
    }

    /**
     * Add custom binary handler
     */
    addBinaryHandler(handler: BinaryHandler): () => void {
        this.binaryHandlers.add(handler);
        return () => this.binaryHandlers.delete(handler);
    }

    /**
     * Check if WebSocket is connected
     */
    get isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    /**
     * Update configuration
     */
    updateConfig(config: Partial<WebSocketConfig>): void {
        this.config = { ...this.config, ...config };

        // If auto-connect changed, update monitoring
        if (config.autoConnect !== undefined) {
            if (config.autoConnect) {
                this.setupAutoConnect();
            } else {
                this.teardownAutoConnect();
            }
        }
    }

    /**
     * Clean up resources
     */
    destroy(): void {
        this.disconnect();
        this.teardownAutoConnect();
        this.messageHandlers.clear();
        this.binaryHandlers.clear();
        this.isInitialized = false;
    }

    // Private methods

    private cleanup(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
            this.healthCheckTimer = null;
        }

        if (this.ws) {
            // Remove event handlers before closing
            this.ws.onopen = null;
            this.ws.onclose = null;
            this.ws.onerror = null;
            this.ws.onmessage = null;

            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.close();
            }
            this.ws = null;
        }
    }

    private setupEventHandlers(): void {
        if (!this.ws) return;

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            store.dispatch(websocketConnected());

            // Send hello message
            this.sendMessage({
                type: 'hello',
                message: 'Skellycam Frontend Connected'
            });

            // Start health check
            this.startHealthCheck();
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            store.dispatch(websocketDisconnected());
            this.stopHealthCheck();

            // Only attempt reconnect if it wasn't an intentional disconnect
            if (!this.intentionalDisconnect) {
                this.attemptReconnect();
            }
        };

        this.ws.onerror = (event) => {
            console.error('WebSocket error:', event);
            store.dispatch(websocketError('WebSocket error occurred'));
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(event.data);
        };
    }

    private handleMessage(data: string | ArrayBuffer): void {
        if (data instanceof ArrayBuffer) {
            // Binary data - route to handlers
            this.binaryHandlers.forEach(handler => handler(data));
        } else if (typeof data === 'string') {
            // Handle ping/pong
            if (data === 'ping') {
                this.send('pong');
                return;
            }

            // Try to parse JSON messages
            try {
                const message = JSON.parse(data) as WebSocketMessage;

                // Process internal handlers first
                this.processInternalMessage(message);

                // Then custom handlers
                this.messageHandlers.forEach(handler => handler(message));
            } catch (error) {
                console.warn('Received non-JSON string message:', data);
            }
        }
    }

    private processInternalMessage(message: WebSocketMessage): void {
        switch (message.message_type) {
            case 'framerate_update':
                this.handleFramerateUpdate(message as FramerateUpdateMessage);
                break;
            case 'log_record':
                this.handleLogRecord(message as LogRecordMessage);
                break;
            default:
                // Unknown message type - let custom handlers deal with it
                console.warn(`Unhandled message type: ${JSON.stringify(message).slice(0, 50)}...`);
                break;
        }
    }

    private handleFramerateUpdate(message: FramerateUpdateMessage): void {
        if (message.backend_framerate) {
            store.dispatch(backendFramerateUpdated(message.backend_framerate));
        }
        if (message.frontend_framerate) {
            store.dispatch(frontendFramerateUpdated(message.frontend_framerate));
        }
    }

    private handleLogRecord(message: LogRecordMessage): void {
        store.dispatch(logAdded(message as LogRecord));
    }

    private attemptReconnect(): void {
        // Don't reconnect if it was intentional or reconnect is disabled
        if (this.intentionalDisconnect || !this.config.reconnect || !this.url) {
            return;
        }

        // Check if server is still alive before attempting reconnect
        const state = store.getState();
        const isServerAlive = selectIsServerAlive(state);

        if (!isServerAlive) {
            console.log('Server not connected, skipping WebSocket reconnect');
            return;
        }

        if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            store.dispatch(websocketError('Max reconnection attempts reached'));
            return;
        }

        this.reconnectAttempts++;
        store.dispatch(websocketReconnecting(this.reconnectAttempts));

        const delay = Math.min(
            this.config.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
            10000
        );

        console.log(`Attempting reconnect ${this.reconnectAttempts}/${this.config.maxReconnectAttempts} in ${delay}ms`);

        this.reconnectTimer = setTimeout(() => {
            if (this.url && !this.intentionalDisconnect) {
                this.connect(this.url);
            }
        }, delay);
    }

    private setupAutoConnect(): void {
        if (!this.config.autoConnect) return;

        // Clean up existing subscription
        this.teardownAutoConnect();

        let lastServerStatus: boolean | null = null;

        // Subscribe to store changes
        this.unsubscribe = store.subscribe(() => {
            const state = store.getState();
            const isServerAlive = selectIsServerAlive(state);

            // Only react to changes in server status
            if (isServerAlive !== lastServerStatus) {
                lastServerStatus = isServerAlive;

                if (isServerAlive && !this.isConnected && !this.intentionalDisconnect) {
                    // Server became available and we're not connected
                    console.log('Server became available, auto-connecting WebSocket');
                    this.connect();
                } else if (!isServerAlive && this.isConnected) {
                    // Server became unavailable while we're connected
                    console.log('Server became unavailable, disconnecting WebSocket');
                    this.intentionalDisconnect = true; // Prevent reconnect attempts
                    this.cleanup();
                    store.dispatch(websocketDisconnected());
                }
            }
        });

        // Check initial state
        const state = store.getState();
        const isServerAlive = selectIsServerAlive(state);
        lastServerStatus = isServerAlive;

        if (isServerAlive && !this.isConnected && !this.intentionalDisconnect) {
            console.log('Server available on init, auto-connecting WebSocket');
            this.connect();
        }
    }

    private teardownAutoConnect(): void {
        if (this.unsubscribe) {
            this.unsubscribe();
            this.unsubscribe = null;
        }
    }

    private startHealthCheck(): void {
        this.stopHealthCheck();

        this.healthCheckTimer = setInterval(() => {
            if (this.isConnected) {
                this.send('ping');
            }
        }, this.config.healthCheckInterval);
    }

    private stopHealthCheck(): void {
        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
            this.healthCheckTimer = null;
        }
    }
}

export const websocketService = WebSocketService.getInstance();
