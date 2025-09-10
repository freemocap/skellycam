// store/middleware/connection-middleware.ts
import {Middleware, Action, UnknownAction} from '@reduxjs/toolkit';
import { websocketService } from '@/services/websocket/websocket-service';
import { connectionOrchestrator } from '@/services/connection/connection-orchestrator';
import {
    serverHealthCheckCompleted,
    websocketConnected,
    websocketDisconnected,
    websocketStatusChanged,
    connectionStatusChanged,
} from '@/store/slices/server/server-slice';

/**
 * Middleware to handle connection lifecycle and auto-reconnection
 */
export const connectionMiddleware: Middleware = (store) => {
    let healthCheckInterval: NodeJS.Timeout | null = null;
    let reconnectAttempt: number = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;
    const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds

    // Initialize services on middleware creation
    websocketService.initialize();

    return (next) => (action: unknown) => {
        const result = next(action);
        const state = store.getState();

        // Handle server connection changes
        if (connectionStatusChanged.match(action)) {
            const status = action.payload;

            if (status === 'connected') {
                // Start health monitoring for the server
                startHealthMonitoring();

                // Auto-connect WebSocket if configured AND we have a managed server
                // For external servers, WebSocket connection is independent
                const isManaged = state.server.connection.mode === 'managed';
                if (state.server.config.autoConnect && isManaged) {
                    setTimeout(() => {
                        if (!websocketService.isConnected) {
                            store.dispatch(websocketStatusChanged('connecting'));
                            websocketService.connect();
                        }
                    }, 1000);
                }
            } else if (status === 'disconnected' || status === 'error') {
                // Stop health monitoring
                stopHealthMonitoring();

                // Only disconnect WebSocket if this was a managed server
                // External WebSocket connections can persist independently
                const wasManaged = state.server.connection.mode === 'managed';
                if (wasManaged && websocketService.isConnected) {
                    console.log('Disconnecting WebSocket due to managed server shutdown');
                    websocketService.disconnect();
                }
                // For external connections, WebSocket stays connected unless explicitly disconnected
            }
        }

        // Handle WebSocket disconnection for auto-reconnect
        if (websocketDisconnected.match(action)) {
            const autoConnect = state.server.config.autoConnect;

            // Try to reconnect if auto-connect is enabled
            // This works regardless of server status - WebSocket can be independent
            if (autoConnect && reconnectAttempt < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempt++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempt - 1), 10000);

                console.log(`WebSocket auto-reconnect attempt ${reconnectAttempt}/${MAX_RECONNECT_ATTEMPTS} in ${delay}ms`);

                setTimeout(() => {
                    if (!websocketService.isConnected) {
                        store.dispatch(websocketStatusChanged('reconnecting'));
                        websocketService.connect();
                    }
                }, delay);
            }
        }

        // Reset reconnect counter on successful connection
        if (websocketConnected.match(action)) {
            reconnectAttempt = 0;
        }

        return result;
    };

    function startHealthMonitoring(): void {
        stopHealthMonitoring();

        healthCheckInterval = setInterval(async () => {
            const state = store.getState();
            const serverUrl = state.server.connection.serverUrl;

            // Only monitor health if we have a server connection
            if (serverUrl && state.server.connection.status === 'connected') {
                const isHealthy = await connectionOrchestrator.checkHealth(serverUrl);
                store.dispatch(serverHealthCheckCompleted(isHealthy));

                if (!isHealthy) {
                    console.error('Server health check failed');
                    store.dispatch(connectionStatusChanged('error'));
                    stopHealthMonitoring();
                }
            }
        }, HEALTH_CHECK_INTERVAL);
    }

    function stopHealthMonitoring(): void {
        if (healthCheckInterval) {
            clearInterval(healthCheckInterval);
            healthCheckInterval = null;
        }
    }
};
