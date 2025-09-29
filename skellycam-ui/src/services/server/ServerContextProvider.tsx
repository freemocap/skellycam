// ServerContextProvider.tsx
import React, {createContext, ReactNode, useContext, useEffect, useRef} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {AppDispatch} from '@/store/types';

import {ConnectionState, WebSocketConnection} from "@/services/server/server-helpers/websocket-connection";
import {FrameProcessor} from "@/services/server/server-helpers/frame-processor/frame-processor";
import {CanvasManager} from "@/services/server/server-helpers/canvas-manager";
import {serverUrls} from "@/services";
import {
    camerasDetectedFromStream,
    cameraMetricsUpdated,
    actualConfigsUpdatedFromStream,
    selectCameras,
    createDefaultCameraConfig,
} from '@/store/slices/cameras';

interface ServerContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    send: (data: string | object) => void;
    setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => void;
}

const ServerContext = createContext<ServerContextValue | null>(null);

export const ServerContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const dispatch = useDispatch<AppDispatch>();
    const cameras = useSelector(selectCameras);

    // Use the service classes
    const wsConnectionRef = useRef<WebSocketConnection>(
        new WebSocketConnection({
            url: serverUrls.getWebSocketUrl(),
            reconnectDelay: 1000,
            maxReconnectAttempts: 5,
            heartbeatInterval: 30000
        })
    );
    const frameProcessorRef = useRef<FrameProcessor>(new FrameProcessor());
    const canvasManagerRef = useRef<CanvasManager>(new CanvasManager());

    useEffect(() => {
        const ws = wsConnectionRef.current;

        // Set up event listeners
        ws.on('state-change', (newState: ConnectionState) => {
            if (newState === ConnectionState.DISCONNECTED || newState === ConnectionState.FAILED) {
                // When disconnected, just clean up resources
                canvasManagerRef.current.terminateAllWorkers();
                frameProcessorRef.current.reset();
            }
        });

        ws.on('message', async (event: MessageEvent) => {
            if (event.data instanceof ArrayBuffer) {
                try {
                    const result = await frameProcessorRef.current.processFramePayload(event.data);
                    if (!result) return;

                    const { frames, cameraIds: seenCameraIds, frameNumbers, configUpdates } = result;

                    // Check if we have new cameras that aren't in the store
                    const newCameraIds = Array.from(seenCameraIds).filter(
                        id => !cameras.find(cam => cam.id === id)
                    );

                    if (newCameraIds.length > 0) {
                        console.log(`Detected new cameras from stream: ${newCameraIds.join(', ')}`);

                        // Get configs for the new cameras from the configUpdates map
                        const newCameraConfigs = newCameraIds.map(id => {
                            const config = configUpdates.get(id);
                            if (config) {
                                return config;
                            } else {
                                // Fallback to default config if not in updates
                                return createDefaultCameraConfig(
                                    id,
                                    parseInt(id),
                                    `Camera ${id}`
                                );
                            }
                        });

                        dispatch(camerasDetectedFromStream(newCameraConfigs));
                    }

                    // Update actual configs for existing cameras if they changed
                    if (configUpdates.size > 0) {
                        dispatch(actualConfigsUpdatedFromStream(configUpdates));
                    }

                    // Send frames to canvas workers and update metrics
                    for (const frameData of frames) {
                        const sent = canvasManagerRef.current.sendFrameToWorker(
                            frameData.cameraId,
                            frameData.bitmap
                        );

                        const camera = cameras.find(cam => cam.id === frameData.cameraId);

                        if (!sent) {
                            frameProcessorRef.current.recordDroppedFrame(frameData.cameraId);
                        }

                        // Update camera metrics if we have frame stats
                        if (camera) {
                            const frameStats = frameProcessorRef.current.getFrameStats(frameData.cameraId);
                            if (frameStats) {
                                dispatch(cameraMetricsUpdated({
                                    cameraId: frameData.cameraId,
                                    fps: frameStats.fps || 0,
                                    droppedFrames: frameStats.droppedFrames || 0,
                                    lastFrameTime: Date.now(),
                                }));
                            }
                        }
                    }

                    if (frameNumbers.size > 1) {
                        console.warn(`Received multiple frame numbers in payload: ${Array.from(frameNumbers).sort((a, b) => a - b).join(', ')}`);
                    }

                    // Acknowledge the highest frame number
                    const maxFrameNumber = Math.max(...Array.from(frameNumbers));
                    ws.send({ type: 'frameAcknowledgment', frameNumber: maxFrameNumber });
                } catch (error) {
                    console.error('Error processing frame:', error);
                }
            }
        });

        // Auto-connect
        ws.connect();

        return () => {
            ws.disconnect();
            canvasManagerRef.current.terminateAllWorkers();
            frameProcessorRef.current.reset();
        };
    }, [dispatch, cameras]);

    return (
        <ServerContext.Provider value={{
            isConnected: wsConnectionRef.current.isConnected(),
            connect: () => wsConnectionRef.current.connect(),
            disconnect: () => wsConnectionRef.current.disconnect(),
            send: (data: string | object) => wsConnectionRef.current.send(data),
            setCanvasForCamera: (cameraId: string, canvas: HTMLCanvasElement) => {
                canvasManagerRef.current.setCanvasForCamera(cameraId, canvas);
            },
        }}>
            {children}
        </ServerContext.Provider>
    );
};

export const useServer = (): ServerContextValue => {
    const context = useContext(ServerContext);
    if (!context) throw new Error('useServer must be used within ServerContextProvider');
    return context;
};
