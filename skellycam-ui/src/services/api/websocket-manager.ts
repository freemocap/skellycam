import {AppDispatch, websocketErrorOccurred, websocketReconnectAttempted, websocketStatusChanged} from "../../store";
import {RootState} from "../../store/types";

export type WebSocketMessageHandler = (data: any) => void;
export type WebSocketBinaryHandler = (data: ArrayBuffer) => void;

class WebSocketManager {
    private static instance: WebSocketManager;
    private ws: WebSocket | null = null;
    private messageHandlers: Set<WebSocketMessageHandler> = new Set();
    private binaryHandlers: Set<WebSocketBinaryHandler> = new Set();
    private reconnectTimeout: NodeJS.Timeout | null = null;
    private dispatch: AppDispatch | null = null;
    private getState: (() => RootState) | null = null;

    private constructor() {}

    static getInstance(): WebSocketManager {
        if (!WebSocketManager.instance) {
            WebSocketManager.instance = new WebSocketManager();
        }
        return WebSocketManager.instance;
    }

    initializeStore(dispatch: AppDispatch, getState: () => RootState): void {
        this.dispatch = dispatch;
        this.getState = getState;
    }

    connect(url: string): void {
        if (this.ws && this.ws.readyState !== WebSocket.CLOSED) {
            return;
        }

        if (!this.dispatch) {
            console.error('WebSocket manager not initialized with store');
            return;
        }

        this.dispatch(websocketStatusChanged('connecting'));

        this.ws = new WebSocket(url);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
            if (this.dispatch) {
                this.dispatch(websocketStatusChanged('connected'));
            }
            this.ws?.send('Hello from Skellycam Frontend 👀📸👋');
            console.log(`WebSocket connected to: ${url}`);
        };

        this.ws.onclose = () => {
            if (this.dispatch) {
                this.dispatch(websocketStatusChanged('disconnected'));
            }
            this.scheduleReconnect(url);
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(event);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            if (this.dispatch) {
                this.dispatch(websocketErrorOccurred('WebSocket connection error'));
            }
        };
    }

    disconnect(): void {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    send(data: string | ArrayBuffer): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(data);
        }
    }

    addMessageHandler(handler: WebSocketMessageHandler): () => void {
        this.messageHandlers.add(handler);
        return () => this.messageHandlers.delete(handler);
    }

    addBinaryHandler(handler: WebSocketBinaryHandler): () => void {
        this.binaryHandlers.add(handler);
        return () => this.binaryHandlers.delete(handler);
    }

    private handleMessage(event: MessageEvent): void {
        const data = event.data;

        if (data instanceof ArrayBuffer) {
            this.binaryHandlers.forEach(handler => handler(data));
        } else if (typeof data === 'string') {
            if (data === 'ping') {
                this.send('pong');
                return;
            }

            try {
                const jsonData = JSON.parse(data);
                this.messageHandlers.forEach(handler => handler(jsonData));
            } catch {
                console.log('Received non-JSON string data:', data);
            }
        }
    }

    private scheduleReconnect(url: string): void {
        if (!this.getState || !this.dispatch) return;

        const state = this.getState();
        if (!state.websocket.shouldReconnect) return;

        this.dispatch(websocketReconnectAttempted());

        const attempt = state.websocket.reconnectAttempt;
        const delay = Math.min(1000 * Math.pow(2, attempt), 10000);

        this.reconnectTimeout = setTimeout(() => {
            console.log(`Reconnecting to WebSocket (attempt #${attempt + 1})`);
            this.connect(url);
        }, delay);
    }

    get isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }
}

export const websocketManager = WebSocketManager.getInstance();
