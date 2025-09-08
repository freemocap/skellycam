export type ServerStatus =
    | 'not-connected'
    | 'spawning'
    | 'shutting-down'
    | 'alive'
    | 'error';

export type WebSocketStatus =
    | 'disconnected'
    | 'connecting'
    | 'connected'
    | 'reconnecting'
    | 'error';

export interface ServerConfig {
    host: string;
    port: number;
    autoConnect: boolean;
}

export interface ServerProcessInfo {
    pid: number | null;
    executablePath: string | null;
}

export interface WebSocketState {
    status: WebSocketStatus;
    error: string | null;
    reconnectAttempts: number;
    lastConnectedAt: string | null;
    lastDisconnectedAt: string | null;
}

export interface ServerState {
    // Configuration (persisted)
    config: ServerConfig;

    // Server process state
    status: ServerStatus;
    errorMessage: string | null;
    retryCount: number;
    lastHealthCheck: string | null;
    processInfo: ServerProcessInfo;

    // WebSocket connection state
    websocket: WebSocketState;
}

