// ServerContextProvider.tsx
import React, { createContext, ReactNode, useContext, useEffect, useRef, useState, useCallback, useMemo } from 'react';

import { ConnectionState, WebSocketConnection } from "@/services/server/server-helpers/websocket-connection";
import { FrameProcessor } from "@/services/server/server-helpers/frame-processor/frame-processor";
import { CanvasManager } from "@/services/server/server-helpers/canvas-manager";
import { serverUrls } from "@/services";
import {FramerateStore} from "@/services/server/server-helpers/framerate-store";
import {DisplayFramerateTracker} from "@/services/server/server-helpers/display-framerate-tracker";
import {LogStore, LogRecord} from "@/services/server/server-helpers/log-store";

interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
    getFps: (cameraId: string) => number | null;
    getServerFps: () => number | null;
    getFramerateStore: () => FramerateStore;
    getLogStore: () => LogStore;
    connectedCameraIds: string[];
    updateServerConnection: (host: string, port: number) => void;
}

const ServerContext = createContext<ServerContextValue | null>(null);

// Compare two already-sorted string arrays without allocating
function sortedArraysEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
        if (a[i] !== b[i]) return false;
    }
    return true;
}

// Type guard to check if a message is a log record
function isLogRecord(data: any): data is LogRecord {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'log_record' &&
        typeof data.levelname === 'string' &&
        typeof data.message === 'string'
    );
}

// Type for framerate update message from backend (backend_framerate only;
// display framerate is measured on the frontend)
interface FramerateUpdateMessage {
    message_type: 'framerate_update';
    camera_group_id: string;
    backend_framerate: {
        mean_frame_duration_ms: number;
        mean_frames_per_second: number;
        frame_duration_max: number;
        frame_duration_min: number;
        frame_duration_mean: number;
        frame_duration_stddev: number;
        frame_duration_median: number;
        frame_duration_coefficient_of_variation: number;
        calculation_window_size: number;
        framerate_source: string;
    };
    frame_durations_ms: number[];
}

// Type guard to check if a message is a framerate update
function isFramerateUpdate(data: any): data is FramerateUpdateMessage {
    return (
        data &&
        typeof data === 'object' &&
        data.message_type === 'framerate_update' &&
        typeof data.camera_group_id === 'string' &&
        data.backend_framerate &&
        typeof data.backend_framerate === 'object' &&
        Array.isArray(data.frame_durations_ms)
    );
}

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    // Reactive state - only updates when camera list actually changes
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [connectedCameraIds, setConnectedCameraIds] = useState<string[]>([]);

    // Service instances
    const wsConnectionRef = useRef<WebSocketConnection | null>(null);
    const frameProcessorRef = useRef<FrameProcessor | null>(null);
    const canvasManagerRef = useRef<CanvasManager | null>(null);
    const framerateStoreRef = useRef<FramerateStore>(new FramerateStore());
    const displayFramerateTrackerRef = useRef<DisplayFramerateTracker>(new DisplayFramerateTracker());
    const logStoreRef = useRef<LogStore>(new LogStore());

    // Latest server-side (backend) FPS stored in a ref for non-reactive access
    const serverFpsRef = useRef<number | null>(null);

    // Holds the latest binary payload received from the WebSocket.
    // The WebSocket onmessage handler writes here synchronously;
    // a separate rAF-driven processing loop reads and clears it.
    // This decouples decoding from the WebSocket message storm,
    // preventing promise starvation where createImageBitmap microtasks
    // can never resolve because the browser dispatches onmessage events
    // back-to-back in a single macrotask without yielding.
    const pendingPayloadRef = useRef<ArrayBuffer | null>(null);
    const processingFrameRef = useRef<boolean>(false);
    const frameLoopRef = useRef<number | null>(null);

    // Cached sorted camera IDs from the last frame — compared by value to avoid
    // per-frame Array.from().sort() allocations when the camera list hasn't changed.
    const lastCameraIdsRef = useRef<string[]>([]);

    // Initialize services once
    useEffect(() => {
        wsConnectionRef.current = new WebSocketConnection({
            url: serverUrls.getWebSocketUrl(),
            reconnectDelay: 1000,
            maxReconnectAttempts: 5,
            heartbeatInterval: 30000
        });
        frameProcessorRef.current = new FrameProcessor();
        canvasManagerRef.current = new CanvasManager();

        return () => {
            if (wsConnectionRef.current) {
                wsConnectionRef.current.disconnect();
            }
            if (canvasManagerRef.current) {
                canvasManagerRef.current.terminateAllWorkers();
            }
            if (frameProcessorRef.current) {
                frameProcessorRef.current.reset();
            }
        };
    }, []);

    // Set up WebSocket connection and handlers
    useEffect(() => {
        const ws = wsConnectionRef.current;
        if (!ws) return;

        const handleStateChange = (newState: ConnectionState): void => {
            const connected = newState === ConnectionState.CONNECTED;
            setIsConnected(connected);

            if (newState === ConnectionState.DISCONNECTED || newState === ConnectionState.FAILED) {
                canvasManagerRef.current?.terminateAllWorkers();
                frameProcessorRef.current?.reset();
                serverFpsRef.current = null;
                processingFrameRef.current = false;
                pendingPayloadRef.current = null;
                lastCameraIdsRef.current = [];
                framerateStoreRef.current.clear();
                displayFramerateTrackerRef.current.clear();
                setConnectedCameraIds([]);
            }
        };

        // Process a decoded frame result: update camera list, dispatch to workers, send ack.
        const dispatchFrames = (
            result: Awaited<ReturnType<FrameProcessor['processFramePayload']>>
        ): void => {
            if (!result) return;

            const { frames, cameraIds, frameNumbers } = result;

            // Only allocate a new sorted array if the camera set actually changed.
            // Compare against the cached ref to avoid Array.from().sort() on every frame.
            const lastIds = lastCameraIdsRef.current;
            let cameraListChanged = lastIds.length !== cameraIds.size;
            if (!cameraListChanged) {
                for (const id of lastIds) {
                    if (!cameraIds.has(id)) {
                        cameraListChanged = true;
                        break;
                    }
                }
            }

            if (cameraListChanged) {
                const newIds = Array.from(cameraIds).sort();
                lastCameraIdsRef.current = newIds;

                setConnectedCameraIds(prevIds => {
                    if (!sortedArraysEqual(prevIds, newIds)) {
                        const removedCameras = prevIds.filter(id => !cameraIds.has(id));
                        for (const cameraId of removedCameras) {
                            canvasManagerRef.current?.terminateWorker(cameraId);
                        }
                        return newIds;
                    }
                    return prevIds;
                });
            }

            for (const frameData of frames) {
                canvasManagerRef.current!.sendFrameToWorker(
                    frameData.cameraId,
                    frameData.bitmap
                );
            }

            // Stamp display framerate at the moment frames are actually
            // decoded and dispatched to canvas workers on the frontend
            const displayTracker = displayFramerateTrackerRef.current;
            displayTracker.stamp();

            const store = framerateStoreRef.current;

            // Push the individual inter-frame duration into the ring buffer
            // for the timeseries and histogram charts
            const lastDuration = displayTracker.lastDurationMs;
            if (lastDuration !== null) {
                store.pushFrontendDuration(lastDuration);
            }

            // Update the rolling-window summary stats for the statistics table
            const displayFramerate = displayTracker.computeFramerate();
            if (displayFramerate) {
                store.updateFrontend(displayFramerate);
            }

            if (frameNumbers.size > 0) {
                const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                ws.send({ type: 'frameAcknowledgment', frameNumber: maxFrameNumber });
            }
        };

        // rAF-driven processing loop. Runs on its own macrotask boundary,
        // so createImageBitmap promises can resolve without being starved
        // by the WebSocket onmessage dispatch loop.
        const processFrameLoop = async (): Promise<void> => {
            if (!processingFrameRef.current && pendingPayloadRef.current !== null) {
                const payload = pendingPayloadRef.current;
                pendingPayloadRef.current = null;
                processingFrameRef.current = true;
                try {
                    const result = await frameProcessorRef.current!.processFramePayload(payload);
                    dispatchFrames(result);
                } catch (error) {
                    console.error('Error processing frame:', error);
                } finally {
                    processingFrameRef.current = false;
                }
            }
            frameLoopRef.current = requestAnimationFrame(processFrameLoop);
        };

        frameLoopRef.current = requestAnimationFrame(processFrameLoop);

        const handleMessage = (event: MessageEvent): void => {
            // Handle binary frame data: just buffer the latest payload.
            // Older unprocessed payloads are overwritten (frame dropping).
            if (event.data instanceof ArrayBuffer) {
                pendingPayloadRef.current = event.data;
            }
            // Handle text/JSON messages (logs, framerate updates, etc.)
            else if (typeof event.data === 'string') {
                // Skip heartbeat pong responses — they're plain text, not JSON
                if (event.data === 'pong') return;

                try {
                    const jsonData = JSON.parse(event.data);

                    // Handle log records
                    if (isLogRecord(jsonData)) {
                        logStoreRef.current.add(jsonData);
                    }
                    // Handle framerate updates
                    else if (isFramerateUpdate(jsonData)) {
                        // Store backend FPS in ref for fast non-reactive access
                        serverFpsRef.current = jsonData.backend_framerate.mean_frames_per_second;
                        const store = framerateStoreRef.current;
                        // Set the summary stats for the "Recent" column
                        store.updateBackend(jsonData.backend_framerate);
                        // Push individual per-frame durations into the ring buffer
                        // for the timeseries and histogram charts
                        store.pushBackendDurations(jsonData.frame_durations_ms);
                        // Display framerate is measured locally in processFrameLoop,
                        // not from the backend message
                    }
                    // Handle other message types
                    else {
                        console.debug('Received unhandled JSON message:', jsonData);
                    }
                } catch (error) {
                    console.error('Error parsing JSON message:', error);
                }
            }
        };

        ws.on('state-change', handleStateChange);
        ws.on('message', handleMessage);

        // Connection is driven by ServerConnectionStatus via the connect() callback.
        // No auto-connect here — the component's autoConnectWs loop handles it.

        return () => {
            ws.off('state-change', handleStateChange);
            ws.off('message', handleMessage);
            ws.disconnect();
            if (frameLoopRef.current !== null) {
                cancelAnimationFrame(frameLoopRef.current);
                frameLoopRef.current = null;
            }
        };
    }, []);

    const connect = useCallback((): void => {
        wsConnectionRef.current?.connect();
    }, []);

    const disconnect = useCallback((): void => {
        wsConnectionRef.current?.disconnect();
    }, []);

    const send = useCallback((data: string | object): void => {
        wsConnectionRef.current?.send(data);
    }, []);

    const setCanvasForCamera = useCallback((cameraId: string, canvas: HTMLCanvasElement): void => {
        canvasManagerRef.current?.setCanvasForCamera(cameraId, canvas);
    }, []);

    const getFps = useCallback((cameraId: string): number | null => {
        return frameProcessorRef.current?.getFps(cameraId) ?? null;
    }, []);

    const getServerFps = useCallback((): number | null => {
        return serverFpsRef.current;
    }, []);

    const getFramerateStore = useCallback((): FramerateStore => {
        return framerateStoreRef.current;
    }, []);

    const getLogStore = useCallback((): LogStore => {
        return logStoreRef.current;
    }, []);

    const updateServerConnection = useCallback((host: string, port: number): void => {
        // Update the singleton so HTTP endpoints also update
        serverUrls.setHost(host);
        serverUrls.setPort(port);

        // Update the WebSocket URL and reconnect
        const ws = wsConnectionRef.current;
        if (ws) {
            ws.disconnect();
            ws.updateUrl(serverUrls.getWebSocketUrl());
            // The auto-reconnect loop in ServerConnectionStatus will re-trigger connect()
        }
    }, []);

    const contextValue = useMemo(() => ({
        isConnected,
        connect,
        disconnect,
        send,
        setCanvasForCamera,
        getFps,
        getServerFps,
        getFramerateStore,
        getLogStore,
        connectedCameraIds,
        updateServerConnection,
    }), [isConnected, connectedCameraIds, connect, disconnect, send, setCanvasForCamera, getFps, getServerFps, getFramerateStore, getLogStore, updateServerConnection]);

    return (
        <ServerContext.Provider value={contextValue}>
            {children}
        </ServerContext.Provider>
    );
};

export const useServer = (): ServerContextValue => {
    const context = useContext(ServerContext);
    if (!context) throw new Error('useServer must be used within ServerContextProvider');
    return context;
};
