import React, { createContext, useContext, useEffect, useRef, ReactNode, useCallback } from 'react';
import {
    CameraImageData, FrameRenderAcknowledgment,
    useWebsocketBinaryMessageProcessor
} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {
    backendFramerateUpdated,
    frontendFramerateUpdated, logAdded,
    selectIsWebSocketConnected,
    useAppDispatch,
    useAppSelector
} from "@/store";
import {WebSocketMessageSchema} from "@/store/slices/websocket/websocket-types";
import {websocketManager} from "@/services/api";

interface WebSocketContextValue {
    isConnected: boolean;
    connect: () => void;
    disconnect: (shouldReconnect?: boolean) => void;
    latestImageData: Record<string, CameraImageData>;
    acknowledgeFrameRendered: (cameraId: string, frameNumber: number) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | undefined>(undefined);

export const WebSocketContextProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const dispatch = useAppDispatch();
    const isConnected = useAppSelector(selectIsWebSocketConnected);

    // Use the binary message processor hook
    const { latestImageData, processBinaryMessage } = useWebsocketBinaryMessageProcessor();

    // Frame acknowledgment tracking
    const latestFrameAcknowledgment = useRef<FrameRenderAcknowledgment | null>(null);
    const latestCameraFrameAcknowledgment = useRef<Record<string, number>>({});

    // Handle JSON messages
    const handleJsonMessage = useCallback((jsonData: unknown) => {
        try {
            const result = WebSocketMessageSchema.safeParse(jsonData);
            if (!result.success) {
                throw new Error("Invalid message format: " + result.error.message);
            }

            const message = result.data;

            switch (message.message_type) {
                case "framerate_update":
                    dispatch(backendFramerateUpdated(message.backend_framerate));
                    dispatch(frontendFramerateUpdated(message.frontend_framerate));
                    break;
                case "log_record":
                    dispatch(logAdded(message));
                    break;
                default:
                    console.log(`Received websocket message of unknown type: ${message}`);
            }
        } catch (error) {
            console.error('Error processing JSON message:', error, jsonData);
        }
    }, [dispatch]);

    // Handle binary messages
    const handleBinaryMessage = useCallback(async (data: ArrayBuffer) => {
        const acknowledgment = await processBinaryMessage(data);
        if (acknowledgment) {
            latestFrameAcknowledgment.current = acknowledgment;
        }
    }, [processBinaryMessage]);

    // Frame acknowledgment handler
    const acknowledgeFrameRendered = useCallback((cameraId: string, frameNumber: number) => {
        latestCameraFrameAcknowledgment.current[cameraId] = frameNumber;

        const allAcknowledged = Object.values(latestCameraFrameAcknowledgment.current).every(
            (acknowledgedFrame) => acknowledgedFrame === latestFrameAcknowledgment.current?.frameNumber
        );

        if (allAcknowledged && latestFrameAcknowledgment.current) {
            // Send acknowledgment on next frame
            setTimeout(() => {
                const acknowledgment = {
                    message_type: 'frame_render_acknowledgment',
                    ...latestFrameAcknowledgment.current
                };
                websocketManager.send(JSON.stringify(acknowledgment));
            }, 0);
        }
    }, []);

    // Setup WebSocket handlers
    useEffect(() => {
        // Add JSON message handler
        const removeJsonHandler = websocketManager.addMessageHandler(handleJsonMessage);

        // Add binary message handler
        const removeBinaryHandler = websocketManager.addBinaryHandler(handleBinaryMessage);

        // Cleanup handlers on unmount
        return () => {
            removeJsonHandler();
            removeBinaryHandler();

            // Clear refs
            latestFrameAcknowledgment.current = null;
            latestCameraFrameAcknowledgment.current = {};
        };
    }, [handleJsonMessage, handleBinaryMessage]);

    const value: WebSocketContextValue = {
        isConnected,
        connect: () => websocketManager.connect(),
        disconnect: (shouldReconnect = true) => websocketManager.disconnect(!shouldReconnect),
        latestImageData,
        acknowledgeFrameRendered,
    };

    return (
        <WebSocketContext.Provider value={value}>
            {children}
        </WebSocketContext.Provider>
    );
};

export const useWebSocketContext = () => {
    const context = useContext(WebSocketContext);
    if (!context) {
        throw new Error('useWebSocketContext must be used within WebSocketContextProvider');
    }
    return context;
};
