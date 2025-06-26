import {useCallback, useEffect, useRef, useState} from 'react';
import {z} from 'zod';
import {FrontendFramePayloadSchema, setLatestFrontendPayload} from '@/store/slices/latestFrontendPayloadSlice';
import {CurrentFramerate, setBackendFramerate, setFrontendFramerate} from "@/store/slices/framerateTrackerSlice";
import {RecordingInfoSchema, setRecordingInfo} from "@/store/slices/recordingInfoSlice";
import {addLog, LogRecordSchema} from "@/store/slices/logRecordsSlice";
import {useAppDispatch} from "@/store/AppStateStore";
import {setCameraStatus, updateCameraConfig} from "@/store/slices/cameras-slices/camerasSlice";
import {CameraConfigSchema} from "@/store/slices/cameras-slices/camera-types";

const MAX_RECONNECT_ATTEMPTS = 30;


export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    // Use state instead of ref to trigger re-renders
    const [latestImageBitmaps, setLatestImageBitmaps] = useState<Record<string, ImageBitmap>>({});

    // Keep a ref for cleanup purposes
    const bitmapCleanupRef = useRef<Record<string, ImageBitmap>>({});
    const dispatch = useAppDispatch();

    const handleIncomingMessage = useCallback((event: MessageEvent, ws:WebSocket) => {
        const data = event.data;
        if (data instanceof Blob) {
            data.text().then(text => {
                parseAndValidateMessage(text, ws);
            }).catch(error => {
                console.error('Error reading Blob data:', error);
            });
        } else if (typeof data === 'string') {
            parseAndValidateMessage(data, ws);
        }
    }, []);

    const parseAndValidateMessage = useCallback(async (data: string, ws:WebSocket) => {
        try {
            const parsedData = JSON.parse(data);

            // First, check if this is a frontend frame payload with jpeg_images
            if (parsedData && typeof parsedData === 'object' && 'jpeg_images' in parsedData) {
                try {
                    // Extract the jpeg_images separately
                    const {jpeg_images, ...payloadData} = parsedData;

                    // Validate the remaining payload data
                    const latestPayload = FrontendFramePayloadSchema.parse(payloadData);

                    // Update state with validated data
                    dispatch(setLatestFrontendPayload(latestPayload));



                    // Process images if they exist - convert directly to ImageBitmap
                    if (jpeg_images && typeof jpeg_images === 'object') {
                        const imagePromises: Promise<[string, ImageBitmap]>[] = [];

                        Object.entries(jpeg_images).forEach(([cameraId, base64String]) => {
                            if (!base64String || typeof base64String !== 'string') return;

                            // Convert base64 to blob
                            const byteString = atob(base64String);
                            const byteArray = new Uint8Array(byteString.length);
                            for (let i = 0; i < byteString.length; i++) {
                                byteArray[i] = byteString.charCodeAt(i);
                            }
                            const blob = new Blob([byteArray], { type: 'image/jpeg' });

                            // Create ImageBitmap from blob
                            const promise = createImageBitmap(blob)
                                .then(bitmap => [cameraId, bitmap] as [string, ImageBitmap]);

                            imagePromises.push(promise);
                        });

                        // Wait for all ImageBitmaps to be created
                        const results = await Promise.all(imagePromises);
                        const newBitmaps: Record<string, ImageBitmap> = {};
                        // Store old bitmaps for cleanup
                        const oldBitmaps = { ...bitmapCleanupRef.current };
                        // Add new bitmaps to the object
                        results.forEach(([cameraId, bitmap]) => {
                            newBitmaps[cameraId] = bitmap;
                        });
                        // Update the cleanup ref with the new bitmaps
                        bitmapCleanupRef.current = { ...newBitmaps };
                        // Update state with new bitmaps
                        setLatestImageBitmaps(newBitmaps);

                        // Clean up old bitmaps in the next tick to avoid blocking
                        queueMicrotask(() => {
                            Object.values(oldBitmaps).forEach(bitmap => {
                                bitmap.close();
                            });
                        });
                        // Send acknowledgment for the received frame, triggering the next one to be sent
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            const ackMessage = JSON.stringify({
                                type: 'received_frame',
                                multi_frame_number: latestPayload.multi_frame_number,
                                received_at: Date.now()
                            });
                            ws.send(ackMessage);
                        } else {
                            console.warn(`Cannot send acknowledgment for frame ${latestPayload.multi_frame_number}: WebSocket not open`);
                        }
                    }


                    return;
                } catch (e) {
                    if (e instanceof z.ZodError) {
                        console.error('FrontendFramePayload validation failed:', {
                            received: parsedData,
                            errors: e.errors
                        });
                    }
                    if (!(e instanceof z.ZodError)) throw e;
                }
            }

            if (parsedData && typeof parsedData === 'object' && 'state_timestamp' in parsedData) {
                try {
                    if (parsedData.camera_configs) {
                        Object.entries(parsedData.camera_configs).forEach(([cameraId, cameraConfig]) => {
                            dispatch(setCameraStatus({cameraId, status: 'CONNECTED'}));
                            dispatch(updateCameraConfig({cameraId, config: CameraConfigSchema.parse(cameraConfig)}));
                        });
                    }
                } catch (e) {

                    if (!(e instanceof z.ZodError)) throw e;
                }
            }

            try {
                const recordingInfo = RecordingInfoSchema.parse(parsedData);
                dispatch(setRecordingInfo(recordingInfo));
                return;
            } catch (e) {

                if (!(e instanceof z.ZodError)) throw e;
            }


            try {
                const logRecord = LogRecordSchema.parse(parsedData);
                dispatch(addLog({
                    message: logRecord.msg,
                    formatted_message: logRecord.formatted_message,
                    severity: logRecord.levelname.toLowerCase() as any,
                    name: logRecord.name,
                    rawMessage: logRecord.msg,
                    args: logRecord.args,
                    pathname: logRecord.pathname,
                    filename: logRecord.filename,
                    module: logRecord.module,
                    lineNumber: logRecord.lineno,
                    functionName: logRecord.funcName,
                    threadName: logRecord.threadName,
                    thread: logRecord.thread,
                    processName: logRecord.processName,
                    process: logRecord.process,
                    stackTrace: logRecord.stack_info,
                    exc_info: logRecord.exc_info,
                    exc_text: logRecord.exc_text,
                    delta_t: logRecord.delta_t,
                }));
                return;
            } catch (e) {
                if (!(e instanceof z.ZodError)) throw e;
            }


            console.error('Message did not match any known schema. Message keys:', Object.keys(parsedData));
        } catch (e) {
            if (e instanceof z.ZodError) {
                console.error('Validation failed with errors:', JSON.stringify(e.errors, null, 2));
            } else {
                console.error(`Failed to parse websocket message: ${e}`);
            }
        }
    }, [dispatch]);

    const connect = useCallback(() => {
        if (websocket && websocket.readyState !== WebSocket.CLOSED) {
            return;
        }
        if (connectAttempt >= MAX_RECONNECT_ATTEMPTS) {
            console.error(`Max reconnection attempts reached. Could not connect to ${wsUrl}`);
            return;
        }
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => {
            setIsConnected(true);
            setConnectAttempt(0);
            ws.send("Hello from the Skellycam Frontend💀📸👋");
            console.log(`Websocket is connected to url: ${wsUrl}`)
        };

        ws.onclose = () => {
            setIsConnected(false);
            setConnectAttempt(prev => prev + 1);
        };

        ws.onmessage = (event) => {
            handleIncomingMessage(event, ws);
        };

        ws.onerror = (error) => {
            console.error('Websocket error:', error);
        };
        setWebSocket(ws);
    }, [wsUrl, websocket, connectAttempt]);

    const disconnect = useCallback(() => {
        if (websocket) {
            websocket.close();
            setWebSocket(null);
        }

    }, [websocket]);

    useEffect(() => {
        const timeout = setTimeout(() => {
            console.log(`Connecting (attempt #${connectAttempt + 1} of ${MAX_RECONNECT_ATTEMPTS}) to websocket at url: ${wsUrl}`);
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 30000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };

    }, [connect, connectAttempt, wsUrl]);

    return {
        isConnected,
        connect,
        disconnect,
        latestImageBitmaps

    };
};
