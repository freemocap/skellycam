// src/store/slices/server/server-types.ts
export type ServerStatus =
    | 'not-connected'
    | 'spawning'
    | 'shutting-down'
    | 'alive'
    | 'error';

export interface ServerConfig {
    host: string;
    port: number;
    autoConnect: boolean;
}

export interface ServerState {
    status: ServerStatus;
    errorMessage: string | null;
    retryCount: number;
    lastHealthCheck: string | null; // ISO timestamp
    config: ServerConfig;
    processInfo: {
        pid: number | null;
        executablePath: string | null;
    };
}




