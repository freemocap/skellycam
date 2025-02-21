import {useCallback, useEffect, useState} from 'react';
import {z} from 'zod';
import {FrontendFramePayloadSchema, JpegImagesSchema} from "@/types/zod-schemas/FrontendFramePayloadSchema";
import {SkellyCamAppStateSchema} from "@/types/zod-schemas/SkellyCamAppStateSchema";
import {setAvailableCameras} from "@/store/slices/availableCamerasSlice";
import {AvailableCamerasSchema} from "@/types/zod-schemas/AvailableCamerasSchema";
import { useAppDispatch } from '@/store/hooks';
import {setFramerate, setIsRecording, setRecordingDirectory} from "@/store/slices/appState";
// import {camerasSetAll} from "@/store/slices/cameraConfigsSlice";
import {LogRecordSchema} from "@/types/zod-schemas/LogRecordSchema";
const MAX_RECONNECT_ATTEMPTS = 20;
const MAX_LOGS = 1000;
export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [latestFrontendPayload, setLatestFrontendPayload] = useState<z.infer<typeof FrontendFramePayloadSchema> | null>(null);
    const [latestImages, setLatestImages] = useState<z.infer<typeof JpegImagesSchema> | null>(null);
    const [latestSkellyCamAppState, setLatestSkellyCamAppState] = useState<z.infer<typeof SkellyCamAppStateSchema> | null>(null);
    const [latestLogs, setLatestLogs] = useState<z.infer<typeof LogRecordSchema> []>([]);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);

    const [connectAttempt, setConnectAttempt] = useState(0);

    const dispatch = useAppDispatch();

    const handleIncomingMessage = (event: MessageEvent) => {
        const data = event.data;
        if (data instanceof Blob) {
            // If data is a Blob, convert it to text
            data.text().then(text => {
                parseAndValidateMessage(text);
            }).catch(error => {
                console.error('Error reading Blob data:', error);
            });
        } else if (typeof data === 'string') {
            parseAndValidateMessage(data);
        } else {
            try {
                const parsedData = JSON.parse(event.data);
                if (parsedData.formatted_message) {
                    setLatestLogs(prevLogs => {
                        if (prevLogs && prevLogs.length > MAX_LOGS) {
                            return [...prevLogs.slice(1), parsedData];
                        } else {
                            return [...(prevLogs || []), parsedData];
                        }
                    });
                }
            } catch (e) {
                console.error('Error parsing JSON data:', e);
            }
        }

    };

    const parseAndValidateMessage = (data: string) => {
        try {
            const parsedData = JSON.parse(data);

            if (parsedData.type === 'FrontendFramePayload') {
                const frontendImagePayload = FrontendFramePayloadSchema.parse(parsedData);
                setLatestFrontendPayload(frontendImagePayload);
                setLatestImages(frontendImagePayload.jpeg_images);
            } else if (parsedData.type === 'SkellycamAppStateDTO') {
                handleNewSkellyCamAppState(parsedData);
            } else if (parsedData.type === 'LogRecord') {
                setLatestLogs(prevLogs => {
                    const updatedLogs = prevLogs ? [...prevLogs, LogRecordSchema.parse(parsedData)] : [LogRecordSchema.parse(parsedData)];
                    return updatedLogs.length > 100 ? updatedLogs.slice(1) : updatedLogs;
                });
            } else {
                console.warn('Received unknown message type:', parsedData.type);
            }
        } catch (e) {
            if (e instanceof z.ZodError) {
                console.error('Validation failed with errors:', JSON.stringify(e.errors, null, 2));
            } else {
                console.log(`Websocket message: ${data}`);
            }
        }
    };

    const handleNewSkellyCamAppState = (parsedData: any) => {
        // TODO - check if the new app state is different from the current state before updating
        const skellycamAppState = SkellyCamAppStateSchema.parse(parsedData);
        setLatestSkellyCamAppState(skellycamAppState);
        if (skellycamAppState.available_devices) {
            dispatch(setAvailableCameras(AvailableCamerasSchema.parse(skellycamAppState.available_devices)));
        }
        if (skellycamAppState.camera_configs) {
            const cameras = Object.values(skellycamAppState.camera_configs);
            // dispatch(camerasSetAll(cameras));
        }
        if (skellycamAppState.current_framerate) {
            dispatch(setFramerate(skellycamAppState.current_framerate));
        }
        if (skellycamAppState.is_recording_flag !== undefined) {
            dispatch(setIsRecording(skellycamAppState.is_recording_flag));
        }
        if (skellycamAppState.record_directory !== undefined) {
            dispatch(setRecordingDirectory(skellycamAppState.record_directory));
        }

    }

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
            console.log(`Websocket is connected to url: ${wsUrl}`)
        };

        ws.onclose = () => {
            setIsConnected(false);
            setConnectAttempt(prev => prev + 1);
        };

        ws.onmessage = (event) => {
            // console.log('Websocket message received with length: ', event.data.length);
            handleIncomingMessage(event);
        };

        ws.onerror = (error) => {
            console.error('Websocket error:', error);
        };

        setWebSocket(ws);
    }, [wsUrl, websocket, connectAttempt]);

    const disconnect = useCallback(()=>{
        if (websocket) {
            websocket.close();
            setWebSocket(null);
        }
    }, [websocket]);

    useEffect(() => {
        const timeout = setTimeout(() => {
            console.log(`Connecting (attempt #${connectAttempt+1} of ${MAX_RECONNECT_ATTEMPTS}) to websocket at url: ${wsUrl}`);
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 30000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };
    }, [connect]);

    return {isConnected, latestFrontendPayload, latestImages,  latestSkellyCamAppState, latestLogs, connect, disconnect};
};
