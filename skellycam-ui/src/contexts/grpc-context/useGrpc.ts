// src/contexts/grpc-context/useGrpc.ts
import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppDispatch } from '@/store/AppStateStore';
import { updateFramerates } from '@/store/slices/framerateTrackerSlice';
import { CameraImageData } from "@/contexts/websocket-context/useWebsocketBinaryMessageProcessor";
import { addGrpcLog } from "@/store/slices/logRecordsSlice";
import { createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";
import { SkellycamService } from "./grpc_generated/skellycam_connect";
import { LogLevel } from "./grpc_generated/skellycam_pb";

// Define the GrpcClient type based on the service
type GrpcClient = ReturnType<typeof createGrpcClient>;

export function createGrpcClient(serverUrl: string) {
  // Create a transport using the Connect protocol
  // This works directly with HTTP/1.1 without needing a proxy
  const transport = createConnectTransport({
    baseUrl: serverUrl,
    // Use JSON format for easier debugging
    useBinaryFormat: false,
  });

  // Create the client
  return createClient(SkellycamService, transport);
}

export const useGrpcClient = (serverUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [client, setClient] = useState<GrpcClient | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const [latestImageData, setLatestImageData] = useState<Record<string, CameraImageData>>({});
    const dispatch = useAppDispatch();

    const latestFrameNumber = useRef<number>(-1);
    const latestCameraFrameAcknowledgment = useRef<Record<string, number>>({});

    // Connect to gRPC server
    const connect = useCallback(() => {
        try {
            const newClient = createGrpcClient(serverUrl);
            setClient(newClient);
            setIsConnected(true);
            setConnectAttempt(0);
            console.log(`gRPC client connected to ${serverUrl}`);
        } catch (error) {
            console.error('Failed to connect to gRPC server:', error);
            setIsConnected(false);
            setConnectAttempt((prev) => prev + 1);
        }
    }, [serverUrl]);

    // Disconnect from gRPC server
    const disconnect = useCallback(() => {
        setClient(null);
        setIsConnected(false);
    }, []);

    // Stream frames
    useEffect(() => {
        if (!client || !isConnected) return;

        const streamFrames = async () => {
            try {
                // Start streaming frames
                const stream = client.streamMultiFrames({
                    displayImageSizes: {},
                    lastReceivedFrameNumber: BigInt(latestFrameNumber.current)
                });

                for await (const response of stream) {
                    // Process frame response
                    const frameNumber = Number(response.frameNumber);
                    const cameraGroupId = response.cameraGroupId;
                    const timestamp = response.timestamp;

                    // Process camera frames
                    const newImageData: Record<string, CameraImageData> = {};

                    for (const cameraFrame of response.cameraFrames) {
                        const cameraId = cameraFrame.cameraId;
                        
                        // Create image bitmap from JPEG data
                        const blob = new Blob([cameraFrame.jpegData], {type: 'image/jpeg'});
                        const imageBitmap = await createImageBitmap(blob);

                        newImageData[cameraId] = {
                            imageBitmap,
                            imageWidth: cameraFrame.imageWidth,
                            imageHeight: cameraFrame.imageHeight,
                            frameNumber: frameNumber,
                            cameraId: cameraId,
                            cameraIndex: cameraFrame.cameraIndex,
                            cameraName: cameraFrame.cameraName,
                        };
                    }

                    // Update state
                    setLatestImageData(newImageData);
                    latestFrameNumber.current = frameNumber;
                }
            } catch (error) {
                console.error('Error in frame streaming:', error);
                setIsConnected(false);
                setConnectAttempt((prev) => prev + 1);
            }
        };

        streamFrames();
    }, [client, isConnected]);

    // Stream logs
    useEffect(() => {
        if (!client || !isConnected) return;

        const streamLogs = async () => {
            try {
                const stream = client.streamLogs({minLevel: LogLevel.INFO});

                for await (const logRecord of stream) {
                    // Use the new action that accepts a gRPC LogRecord directly
                    dispatch(addGrpcLog(logRecord));
                }
            } catch (error) {
                console.error('Error in log streaming:', error);
            }
        };

        streamLogs();
    }, [client, isConnected, dispatch]);

    // Stream framerates
    useEffect(() => {
        if (!client || !isConnected) return;

        const streamFramerates = async () => {
            try {
                const stream = client.streamFramerates({
                    cameraGroupId: ''
                });

                for await (const update of stream) {
                    // Dispatch framerate updates to Redux store
                    if (update.backendFramerate) {
                        dispatch(updateFramerates(update));
                    }
                }
            } catch (error) {
                console.error('Error in framerate streaming:', error);
            }
        };

        streamFramerates();
    }, [client, isConnected, dispatch]);

    // Handle frame acknowledgment
    const acknowledgeFrameRendered = useCallback(
        (cameraId: string, frameNumber: number) => {
            if (!client || !isConnected) return;

            latestCameraFrameAcknowledgment.current[cameraId] = frameNumber;
            const allAcknowledged = Object.values(latestCameraFrameAcknowledgment.current).every(
                (acknowledgedFrame) => acknowledgedFrame === latestFrameNumber.current
            );

            if (allAcknowledged && latestFrameNumber.current >= 0) {
                // Send acknowledgment to server
                client.acknowledgeMultiFrame({
                    frameNumber: BigInt(latestFrameNumber.current),
                    displayImageSizes: {}
                }).then(() => {
                    // Acknowledgment sent successfully
                }).catch((error: any) => {
                    console.error('Error sending frame acknowledgment:', error);
                });
            }
        },
        [client, isConnected]
    );

    // Reconnect with exponential backoff
    useEffect(() => {
        if (isConnected) return;

        const timeout = setTimeout(() => {
            console.log(`Connecting to gRPC server at ${serverUrl} (attempt #${connectAttempt + 1})`);
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 10000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };
    }, [connect, connectAttempt, isConnected, serverUrl]);

    return {
        isConnected,
        connect,
        disconnect,
        latestImageData,
        acknowledgeFrameRendered
    };
};