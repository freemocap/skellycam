
// ============================================
//  REACT HOOK (use-websocket.ts)
// ============================================

import { useCallback } from 'react';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { websocketService } from './websocket-service';
import {
    selectWebSocketError,
    selectWebSocketStatus,
    websocketStatusChanged
} from '@/store';

export function useWebSocket() {
    const dispatch = useAppDispatch();
    const status = useAppSelector(selectWebSocketStatus);
    const error = useAppSelector(selectWebSocketError);

    const connect = useCallback(() => {
        dispatch(websocketStatusChanged('connecting'));
        websocketService.connect();
    }, [dispatch]);

    const disconnect = useCallback(() => {
        websocketService.disconnect();
    }, []);

    const send = useCallback((data: string | object) => {
        if (typeof data === 'string') {
            websocketService.send(data);
        } else {
            websocketService.sendMessage(data);
        }
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
