import React, { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    websocketConnected,
    websocketDisconnected,
    selectServerConfig,
    selectIsServerAlive,
} from '@/store';
import { ParsedFrame, parseFramePayload } from "@/services/websocket/frame-parser";

type FrameHandler = (frame: ParsedFrame) => void;


interface WebSocketContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    subscribeToFrames: (cameraId: string, handler: FrameHandler) => () => void;
    cameraIds: string[];
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const dispatch = useDispatch();
    const serverConfig = useSelector(selectServerConfig);
    const isServerAlive = useSelector(selectIsServerAlive);

    const wsRef = useRef<WebSocket | null>(null);
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [cameraIds, setCameraIds] = useState<string[]>([]);

    const frameHandlersRef = useRef<Map<string, Set<FrameHandler>>>(new Map());
    const textDecoderRef = useRef<TextDecoder>(new TextDecoder());

    const connect = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const url = `ws://${serverConfig.host}:${serverConfig.port}/skellycam/websocket/connect`;
        const ws = new WebSocket(url);
        ws.binaryType = 'arraybuffer';
        wsRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            dispatch(websocketConnected());
        };

        ws.onclose = () => {
            setIsConnected(false);
            dispatch(websocketDisconnected());
            // Clear camera data on disconnect
            setCameraIds([]);
        };

        ws.onmessage = async (event: MessageEvent) => {
            if (event.data instanceof ArrayBuffer) {
                // Binary frame data
                const frames = await parseFramePayload(event.data, textDecoderRef.current);
                if (!frames) return;

                // Track cameras and update metadata
                const seenCameraIds = new Set<string>();

                for (const frameData of frames) {
                    seenCameraIds.add(frameData.cameraId);

                    // Notify handlers
                    const handlers = frameHandlersRef.current.get(frameData.cameraId);
                    if (!handlers) continue;
                    handlers.forEach(handler => handler(frameData));
                }

                // Update camera IDs only if they changed
                const newCameraIds = Array.from(seenCameraIds).sort();

                if (JSON.stringify(newCameraIds) !== JSON.stringify(cameraIds)) {
                    setCameraIds(newCameraIds);
                }
            }
        };
    };

    const disconnect = () => {
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    };

    const send = (data: string | object) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const payload = typeof data === 'string' ? data : JSON.stringify(data);
            wsRef.current.send(payload);
        }
    };

    const subscribeToFrames = (cameraId: string, handler: FrameHandler): (() => void) => {
        if (!frameHandlersRef.current.has(cameraId)) {
            frameHandlersRef.current.set(cameraId, new Set());
        }
        frameHandlersRef.current.get(cameraId)!.add(handler);

        return () => {
            frameHandlersRef.current.get(cameraId)?.delete(handler);
            // Clean up empty handler sets
            if (frameHandlersRef.current.get(cameraId)?.size === 0) {
                frameHandlersRef.current.delete(cameraId);
            }
        };
    };

    // Auto-connect when server is available
    useEffect(() => {
        if (isServerAlive && !isConnected) {
            connect();
        }

        return () => {
            if (isConnected) {
                disconnect();
            }
        };
    }, [isServerAlive]);

    return (
        <WebSocketContext.Provider value={{
            isConnected,
            connect,
            disconnect,
            send,
            subscribeToFrames,
            cameraIds,
        }}>
            {children}
        </WebSocketContext.Provider>
    );
};

export const useWebSocket = (): WebSocketContextValue => {
    const context = useContext(WebSocketContext);
    if (!context) throw new Error('useWebSocket must be used within WebSocketProvider');
    return context;
};
