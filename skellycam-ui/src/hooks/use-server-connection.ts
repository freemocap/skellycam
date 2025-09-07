import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {selectIsWebSocketConnected} from "@/store/slices/websocket";
import {
    checkServerHealth,
    selectIsServerAlive,
    selectServerConfig,
    selectServerStatus,
    startServer
} from "@/store/slices/server";
import {websocketManager} from "@/services/api";
import {electronAPI} from "@/hooks/electron-service/electron-api";

/**
 * Hook to manage server and WebSocket connection lifecycle
 */
export function useServerConnection() {
    const dispatch = useAppDispatch();
    const serverStatus = useAppSelector(selectServerStatus);
    const serverConfig = useAppSelector(selectServerConfig);
    const isServerAlive = useAppSelector(selectIsServerAlive);
    const isWebSocketConnected = useAppSelector(selectIsWebSocketConnected);

    // Auto-start server on mount if configured
    useEffect(() => {
        const autoStart = async () => {
            if (!serverConfig.autoConnect) return;
            if (serverStatus !== 'not-connected') return;

            // Check if server is already running
            const isHealthy = await dispatch(checkServerHealth()).unwrap();
            if (isHealthy) {
                // Server is running, connect WebSocket
                websocketManager.connect();
                return;
            }

            // Try to start server if we have Electron API
            if (electronAPI) {
                try {
                    const currentPath = await electronAPI.pythonServer.getExecutablePath.query();
                    if (currentPath) {
                        await dispatch(startServer({ exePath: currentPath })).unwrap();
                        // WebSocket will auto-connect after server starts
                    }
                } catch (error) {
                    console.error('Failed to auto-start server:', error);
                }
            }
        };

        autoStart();
    }, []); // Only run once on mount

    // Auto-connect WebSocket when server becomes alive
    useEffect(() => {
        if (isServerAlive && !isWebSocketConnected && serverConfig.autoConnect) {
            setTimeout(() => websocketManager.connect(), 500);
        }
    }, [isServerAlive, isWebSocketConnected, serverConfig.autoConnect]);

    // Periodic health checks when WebSocket is disconnected
    useEffect(() => {
        if (!isWebSocketConnected && isServerAlive) {
            const interval = setInterval(() => {
                dispatch(checkServerHealth());
            }, 5000);

            return () => clearInterval(interval);
        }
    }, [isWebSocketConnected, isServerAlive, dispatch]);

    return {
        serverStatus,
        isServerAlive,
        isWebSocketConnected,
    };
}
