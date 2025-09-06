import { useCallback, useEffect, useState, useRef } from "react";
import { useWebSocketContext } from "@/context/websocket-context/WebSocketContext";
import { serverHealthcheck } from "@/store/thunks/server-healthcheck";
import { shutdownServer } from "@/store/thunks/shutdown-server";
import { electronIpcClient } from "@/hooks/electron-service/electron-ipc-client";
import { useServerConfig } from "@/hooks/useServerConfig";

export type ServerStatus = 'not-connected' | 'spawning' | 'shutting-down' | 'alive' | 'error';

interface ServerState {
    status: ServerStatus;
    errorMessage: string | null;
    retryCount: number;
    lastHealthCheck: Date | null;
}

const MAX_RETRIES = 10;
const RETRY_DELAY = 1000;
const HEALTH_CHECK_INTERVAL = 5000; // Check every 5 seconds when not connected

export const usePythonServer = () => {
    const { isConnected, connect } = useWebSocketContext();
    const { config } = useServerConfig();

    const [state, setState] = useState<ServerState>({
        status: 'not-connected',
        errorMessage: null,
        retryCount: 0,
        lastHealthCheck: null,
    });

    const healthCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const isTransitioningRef = useRef(false);

    // Update status helper
    const updateState = useCallback((updates: Partial<ServerState>) => {
        setState(prev => ({ ...prev, ...updates }));
    }, []);

    // Clear health check interval
    const clearHealthCheckInterval = useCallback(() => {
        if (healthCheckIntervalRef.current) {
            clearInterval(healthCheckIntervalRef.current);
            healthCheckIntervalRef.current = null;
        }
    }, []);

    // Health check with retry logic
    const checkServerHealth = useCallback(async (): Promise<boolean> => {
        // If WebSocket is connected, server is definitely alive
        if (isConnected) {
            updateState({
                status: 'alive',
                errorMessage: null,
                retryCount: 0,
                lastHealthCheck: new Date()
            });
            return true;
        }

        // Try health check endpoint
        try {
            const response = await serverHealthcheck();
            if (response?.ok) {
                updateState({
                    status: 'alive',
                    errorMessage: null,
                    retryCount: 0,
                    lastHealthCheck: new Date()
                });
                return true;
            }
        } catch (error) {
            console.debug('Health check failed:', error);
        }

        // Server not responding
        updateState({
            status: 'not-connected',
            lastHealthCheck: new Date()
        });
        return false;
    }, [isConnected, updateState]);

    // Start server with proper lifecycle management
    const startPythonServer = useCallback(async (exePath: string | null = null): Promise<boolean> => {
        if (isTransitioningRef.current) {
            console.warn('Server transition already in progress');
            return false;
        }

        isTransitioningRef.current = true;
        updateState({ status: 'spawning', errorMessage: null, retryCount: 0 });

        try {
            // First try to shutdown any existing server
            try {
                await shutdownServer();
                await new Promise(resolve => setTimeout(resolve, 500));
            } catch {
                // Ignore shutdown errors
            }

            // Start the server
            await electronIpcClient.pythonServer.start.mutate({ exePath });

            // Wait for server to be ready with retries
            for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
                updateState({ retryCount: attempt });

                await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));

                const isHealthy = await checkServerHealth();
                if (isHealthy) {
                    updateState({ status: 'alive', errorMessage: null, retryCount: 0 });

                    // Auto-connect WebSocket if configured
                    if (config.autoConnect && !isConnected) {
                        setTimeout(() => connect(), 500);
                    }

                    isTransitioningRef.current = false;
                    return true;
                }
            }

            // Failed after all retries
            throw new Error(`Server failed to start after ${MAX_RETRIES} attempts`);

        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Unknown error';
            updateState({
                status: 'error',
                errorMessage: `Failed to start server: ${errorMsg}`,
                retryCount: 0
            });
            console.error('Failed to start Python server:', error);
            isTransitioningRef.current = false;
            return false;
        }
    }, [checkServerHealth, config.autoConnect, isConnected, connect, updateState]);

    // Stop server with proper cleanup
    const stopPythonServer = useCallback(async (): Promise<boolean> => {
        if (isTransitioningRef.current) {
            console.warn('Server transition already in progress');
            return false;
        }

        isTransitioningRef.current = true;
        updateState({ status: 'shutting-down', errorMessage: null });

        try {
            // First disconnect WebSocket if connected
            if (isConnected) {
                // This will be handled by the WebSocketContext
            }

            // Shutdown via HTTP endpoint first (graceful)
            try {
                await shutdownServer();
                await new Promise(resolve => setTimeout(resolve, 500));
            } catch {
                // If HTTP shutdown fails, continue with force stop
            }

            // Force stop via IPC
            await electronIpcClient.pythonServer.stop.mutate();

            updateState({ status: 'not-connected', errorMessage: null });
            isTransitioningRef.current = false;
            return true;

        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Unknown error';
            updateState({
                status: 'error',
                errorMessage: `Failed to stop server: ${errorMsg}`
            });
            console.error('Failed to stop Python server:', error);
            isTransitioningRef.current = false;
            return false;
        }
    }, [isConnected, updateState]);

    // Auto-start logic on mount
    useEffect(() => {
        const autoStartServer = async () => {
            // Skip if already operational or transitioning
            if (state.status === 'alive' ||
                state.status === 'spawning' ||
                state.status === 'shutting-down' ||
                isConnected) {
                return;
            }

            // First try to connect to existing server
            const isHealthy = await checkServerHealth();
            if (isHealthy) {
                if (config.autoConnect) {
                    connect();
                }
                return;
            }

            // If configured for auto-start, try to start server
            if (config.autoConnect) {
                try {
                    const currentPath = await electronIpcClient.pythonServer.getExecutablePath.query();
                    if (currentPath) {
                        await startPythonServer(currentPath);
                    } else {
                        // Try to find a valid executable
                        const candidates = await electronIpcClient.pythonServer.getExecutableCandidates.query();
                        const validCandidate = candidates.find((c: any) => c.isValid);
                        if (validCandidate) {
                            await startPythonServer(validCandidate.path);
                        }
                    }
                } catch (error) {
                    console.error("Error during auto-start:", error);
                }
            }
        };

        autoStartServer();
    }, []); // Only run once on mount

    // Periodic health checks when not connected
    useEffect(() => {
        if (isConnected) {
            // WebSocket connected, server is alive
            updateState({ status: 'alive', errorMessage: null });
            clearHealthCheckInterval();
        } else if (state.status === 'alive') {
            // Lost WebSocket connection but server might still be alive
            // Start periodic health checks
            clearHealthCheckInterval();
            healthCheckIntervalRef.current = setInterval(() => {
                checkServerHealth();
            }, HEALTH_CHECK_INTERVAL);
        } else if (state.status === 'not-connected') {
            // Periodic checks to detect if server comes online
            clearHealthCheckInterval();
            healthCheckIntervalRef.current = setInterval(() => {
                checkServerHealth();
            }, HEALTH_CHECK_INTERVAL);
        }

        return () => clearHealthCheckInterval();
    }, [isConnected, state.status, checkServerHealth, clearHealthCheckInterval, updateState]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            clearHealthCheckInterval();
        };
    }, [clearHealthCheckInterval]);

    return {
        serverStatus: state.status,
        errorMessage: state.errorMessage,
        isPythonRunning: state.status === 'alive',
        isTransitioning: state.status === 'spawning' || state.status === 'shutting-down',
        retryCount: state.retryCount,
        lastHealthCheck: state.lastHealthCheck,
        startPythonServer,
        stopPythonServer,
        checkServerHealth,
    };
};
