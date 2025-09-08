
import { store } from '@/store';
import {
    websocketConnected,
    websocketDisconnected,
    websocketError,
    websocketReconnecting,
} from '@/store';
import {WebSocketMessage} from "@/services/websocket/websocket-types";

export type MessageHandler = (data: WebSocketMessage) => void;
export type BinaryHandler = (data: ArrayBuffer) => void;

interface WebSocketConfig {
    reconnect: boolean;
    reconnectInterval: number;
    maxReconnectAttempts: number;
}

class WebSocketManager {
    private static instance: WebSocketManager;
    private ws: WebSocket | null = null;
    private messageHandlers = new Set<MessageHandler>();
    private binaryHandlers = new Set<BinaryHandler>();
    private reconnectTimer: NodeJS.Timeout | null = null;
    private reconnectAttempts = 0;
    private config: WebSocketConfig = {
        reconnect: true,
        reconnectInterval: 1000,
        maxReconnectAttempts: 10,
    };
    private url: string | null = null;

    private constructor() {}

    static getInstance(): WebSocketManager {
        if (!WebSocketManager.instance) {
            WebSocketManager.instance = new WebSocketManager();
        }
        return WebSocketManager.instance;
    }

    connect(url: string): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            return;
        }

        this.url = url;
        this.cleanup();

        try {
            this.ws = new WebSocket(url);
            this.ws.binaryType = 'arraybuffer';
            this.setupEventHandlers();
        } catch (error) {
            store.dispatch(websocketError(error instanceof Error ? error.message : 'Connection failed'));
        }
    }

    disconnect(): void {
        this.config.reconnect = false;
        this.cleanup();
        store.dispatch(websocketDisconnected());
    }

    private cleanup(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    private setupEventHandlers(): void {
        if (!this.ws) return;

        this.ws.onopen = () => {
            this.reconnectAttempts = 0;
            store.dispatch(websocketConnected());
            this.send(JSON.stringify({ type: 'hello', message: 'Skellycam Frontend Connected' }));
        };

        this.ws.onclose = () => {
            store.dispatch(websocketDisconnected());
            this.attemptReconnect();
        };

        this.ws.onerror = (event) => {
            store.dispatch(websocketError('WebSocket error occurred'));
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(event.data);
        };
    }

    private handleMessage(data: string | ArrayBuffer): void {
        if (data instanceof ArrayBuffer) {
            // Binary data - goes directly to handlers, never to Redux
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
                this.messageHandlers.forEach(handler => handler(message));
            } catch {
                console.warn('Received non-JSON string message:', data);
            }
        }
    }

    private attemptReconnect(): void {
        if (!this.config.reconnect || !this.url) return;
        if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
            store.dispatch(websocketError('Max reconnection attempts reached'));
            return;
        }

        this.reconnectAttempts++;
        store.dispatch(websocketReconnecting(this.reconnectAttempts));

        const delay = Math.min(
            this.config.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
            10000
        );

        this.reconnectTimer = setTimeout(() => {
            if (this.url) {
                this.connect(this.url);
            }
        }, delay);
    }

    send(data: string | ArrayBuffer): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(data);
        }
    }

    addMessageHandler(handler: MessageHandler): () => void {
        this.messageHandlers.add(handler);
        return () => this.messageHandlers.delete(handler);
    }

    addBinaryHandler(handler: BinaryHandler): () => void {
        this.binaryHandlers.add(handler);
        return () => this.binaryHandlers.delete(handler);
    }

    get isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    updateConfig(config: Partial<WebSocketConfig>): void {
        this.config = { ...this.config, ...config };
    }

    acknowledgeFrameRendered(cameraId: string, frameNumber: number): void {
        this.send(JSON.stringify({
            type: 'frame_ack',
            camera_id: cameraId,
            frame_number: frameNumber,
        }));
    }
}

export const websocketManager = WebSocketManager.getInstance();
