import React, { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    websocketConnected,
    websocketDisconnected,
    selectServerConfig,
    selectIsServerAlive,
} from '@/store';
import { parseMultiFramePayload } from "@/services/websocket/frame-parser";
import {workerCode} from "@/services/websocket/offscreen-renderer.worker";

interface WebSocketContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    cameraIds: string[];
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const dispatch = useDispatch();
    const serverConfig = useSelector(selectServerConfig);
    const isServerAlive = useSelector(selectIsServerAlive);

    const wsRef = useRef<WebSocket | null>(null);
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [cameraIds, setCameraIds] = useState<string[]>([]);

    const workersRef = useRef<Map<string, Worker>>(new Map());
    const canvasesRef = useRef<Map<string, HTMLCanvasElement>>(new Map());

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
            // Clean up workers
            workersRef.current.forEach(worker => worker.terminate());
            workersRef.current.clear();
            canvasesRef.current.clear();
        };

        ws.onmessage = async (event: MessageEvent) => {
            if (event.data instanceof ArrayBuffer) {
                try {
                    // Binary frame data
                    const frames = await parseMultiFramePayload(event.data);
                    if (!frames) return;

                    // Track cameras and update metadata
                    const seenCameraIds = new Set<string>();
                    const frameNumbers = new Set<number>();
                    for (const frameData of frames) {
                        seenCameraIds.add(frameData.cameraId);
                        frameNumbers.add(frameData.frameNumber);

                        // Send to worker if exists
                        const worker = workersRef.current.get(frameData.cameraId);
                        if (worker) {
                            console.log(`Sending frame ${frameData.frameNumber} of camera ${frameData.cameraId} to worker with size ${frameData.width}x${frameData.height}`);
                            worker.postMessage({
                                type: 'frame',
                                bitmap: frameData.bitmap
                            }, [frameData.bitmap]);
                        } else {
                            // Clean up bitmap if no worker to handle it
                            frameData.bitmap.close();
                        }
                    }

                    // Update camera IDs only if they changed
                    const newCameraIds = Array.from(seenCameraIds).sort();
                    const changed = newCameraIds.length !== cameraIds.length ||
                        newCameraIds.some((id, i) => id !== cameraIds[i]);

                    if (changed) {
                        console.log(`Detected cameras: ${newCameraIds.join(', ')}`);
                        setCameraIds(newCameraIds);
                    }
                    if (frameNumbers.size > 1) {
                        console.warn(`Received multiple frame numbers in payload: ${Array.from(frameNumbers).sort((a, b) => a - b).join(', ')}`);
                    }
                    // Acknowledge the highest frame number received
                    const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                    sendFrameAcknowledgment(maxFrameNumber);
                } catch (error) {
                    console.error('Error processing frame:', error);
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

    const sendFrameAcknowledgment = (frameNumber: number) => {
        console.debug(`Acknowledging frame ${frameNumber}`);
        send({ type: 'frameAcknowledgment', frameNumber });
    }

    const setCanvasForCamera = (cameraId: string, canvas: HTMLCanvasElement) => {
        // Check if this exact canvas is already being used for this camera
        const existingCanvas = canvasesRef.current.get(cameraId);
        if (existingCanvas === canvas) {
            // This canvas is already set up for this camera, nothing to do
            return;
        }

        // Clean up existing worker if switching to a different canvas
        const existingWorker = workersRef.current.get(cameraId);
        if (existingWorker) {
            existingWorker.terminate();
            workersRef.current.delete(cameraId);
        }

        try {
            // Create worker that handles offscreen rendering
            const blob = new Blob([workerCode], { type: 'application/javascript' });
            const workerUrl = URL.createObjectURL(blob);
            const worker = new Worker(workerUrl);

            // Transfer canvas to worker
            const offscreen = canvas.transferControlToOffscreen();
            worker.postMessage({ type: 'init', canvas: offscreen }, [offscreen]);

            // Store worker and canvas reference
            workersRef.current.set(cameraId, worker);
            canvasesRef.current.set(cameraId, canvas);

            // Clean up blob URL
            URL.revokeObjectURL(workerUrl);
        } catch (error) {
            console.error(`Failed to create worker for camera ${cameraId}:`, error);
        }
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
            cameraIds,
            setCanvasForCamera,
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
