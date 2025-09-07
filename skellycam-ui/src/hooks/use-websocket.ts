import { useCallback } from 'react';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {
    selectIsWebSocketConnecting,
    selectWebSocketReconnectAttempt,
    selectWebSocketStatus,
    useAppSelector
} from "@/store";
import {websocketManager} from "@/services/api";

/**
 * Hook for WebSocket operations with Redux state
 */
export function useWebSocket() {
    const context = useWebSocketContext();
    const status = useAppSelector(selectWebSocketStatus);
    const reconnectAttempt = useAppSelector(selectWebSocketReconnectAttempt);
    const isConnecting = useAppSelector(selectIsWebSocketConnecting);

    const sendMessage = useCallback((message: string | object) => {
        const data = typeof message === 'string' ? message : JSON.stringify(message);
        websocketManager.send(data);
    }, []);

    return {
        ...context,
        status,
        reconnectAttempt,
        isConnecting,
        sendMessage,
    };
}

// Export everything from the WebSocket context
export * from '../../hooks/websocket-binary-processor';
