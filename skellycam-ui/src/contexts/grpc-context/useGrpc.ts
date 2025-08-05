// skellycam-ui/src/contexts/grpc-context/useGrpc.ts
import {CompatServiceDefinition, createChannel, createClient} from 'nice-grpc';
import {SkellycamServiceClient} from './grpc_generated/skellycam';
import {useCallback, useEffect, useRef, useState} from 'react';
import {useAppDispatch} from '@/store/AppStateStore';
import {updateFramerates} from '@/store/slices/framerateTrackerSlice';
import {CameraImageData} from "@/contexts/websocket-context/useWebsocketBinaryMessageProcessor";
import {addGrpcLog} from "@/store/slices/logRecordsSlice";
// Define the service definition object
const SkellycamServiceDefinition = {
    serviceName: "skellycam.SkellycamService",
    methods: {
        streamMultiFrames: {
            path: "/skellycam.SkellycamService/streamMultiFrames",
            requestStream: false,
            responseStream: true,
        },
        acknowledgeMultiFrame: {
            path: "/skellycam.SkellycamService/acknowledgeMultiFrame",
            requestStream: false,
            responseStream: false,
        },
        streamLogs: {
            path: "/skellycam.SkellycamService/streamLogs",
            requestStream: false,
            responseStream: true,
        },
        streamFramerates: {
            path: "/skellycam.SkellycamService/streamFramerates",
            requestStream: false,
            responseStream: true,
        }
    }
} as const;

// Create gRPC channel and client
const createGrpcClient = (serverUrl: string) => {
    const channel = createChannel(serverUrl);
    return createClient(SkellycamServiceDefinition, channel);
};

export const useGrpcClient = (serverUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [client, setClient] = useState<ReturnType<typeof createGrpcClient> | null>(null);
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

    // Start streaming frames
    useEffect(() => {
        if (!client || !isConnected) return;

        const streamFrames = async () => {
            try {
                // Convert display image sizes to the format expected by the server
                const displayImageSizes: Record<string, { width: number, height: number }> = {};

                // Start streaming frames
                const stream = client.streamMultiFrames({
                    displayImageSizes,
                    lastReceivedFrameNumber: latestFrameNumber.current
                });

                for await (const response of stream) {
                    // Process frame response
                    const frameNumber = response.frameNumber;
                    const cameraGroupId = response.cameraGroupId;
                    const timestamp = response.timestamp;

                    // Process camera frames
                    const newImageData: Record<string, CameraImageData> = {};

                    for (const cameraFrame of response.cameraFrames) {
                        const cameraId = cameraFrame.cameraId;
                        const cameraName = cameraFrame.cameraName;

                        // Create image bitmap from JPEG data
                        const blob = new Blob([cameraFrame.jpegData], {type: 'image/jpeg'});
                        const imageBitmap = await createImageBitmap(blob);

                        newImageData[cameraId] = {
                            imageBitmap,
                            imageWidth: cameraFrame.imageWidth,
                            imageHeight: cameraFrame.imageHeight,
                            frameNumber: frameNumber,
                            cameraId: cameraId,
                            cameraName: cameraName,
                            cameraIndex: cameraFrame.cameraIndex
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

    // Start streaming logs

    useEffect(() => {
        if (!client || !isConnected) return;

        const streamLogs = async () => {
            try {
                const stream = client.streamLogs({minLevel: 2}); // INFO level

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
    // Start streaming framerates
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
                const displayImageSizes: Record<string, { width: number, height: number }> = {};

                client.acknowledgeMultiFrame({
                    frameNumber: latestFrameNumber.current,
                    displayImageSizes
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
