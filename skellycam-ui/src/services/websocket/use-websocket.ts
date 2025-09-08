
// ============================================
//  REACT HOOK (use-websocket.ts)
// ============================================
// Clean hook for React components

import { useCallback, useEffect } from 'react';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import {websocketService} from "@/services/websocket/websocket-service";
import {selectWebSocketError, selectWebSocketStatus} from "@/store";
import {frameRouter, websocketManager} from "@/services";


export function useWebSocket() {
    const dispatch = useAppDispatch();
    const status = useAppSelector(selectWebSocketStatus);
    const error = useAppSelector(selectWebSocketError);

    const connect = useCallback(() => {
        websocketService.connect();
    }, []);

    const disconnect = useCallback(() => {
        websocketService.disconnect();
    }, []);

    const send = useCallback((data: string | object) => {
        const message = typeof data === 'string' ? data : JSON.stringify(data);
        websocketManager.send(message);
    }, []);

    return {
        status,
        error,
        isConnected: status === 'connected',
        isConnecting: status === 'connecting' || status === 'reconnecting',
        connect,
        disconnect,
        send,
    };
}

