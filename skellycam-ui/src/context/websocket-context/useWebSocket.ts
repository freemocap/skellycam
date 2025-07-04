import {useCallback, useEffect, useRef, useState} from 'react';
import {z} from 'zod';
import {FrontendFramePayloadSchema, setLatestFrontendPayload} from '@/store/slices/latestFrontendPayloadSlice';
import {CurrentFramerate, setBackendFramerate, setFrontendFramerate} from "@/store/slices/framerateTrackerSlice";
import {RecordingInfoSchema, setRecordingInfo} from "@/store/slices/recordingInfoSlice";
import {addLog, LogRecordSchema} from "@/store/slices/logRecordsSlice";
import {useAppDispatch} from "@/store/AppStateStore";
import {setCameraStatus, updateCameraConfig} from "@/store/slices/cameras-slices/camerasSlice";
import {CameraConfigSchema} from "@/store/slices/cameras-slices/camera-types";
import {useWebsocketBinaryMessageProcessor} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

const MAX_RECONNECT_ATTEMPTS = 30;


export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const dispatch = useAppDispatch();

    const {
        latestImageBitmaps,
        lastProcessedFrameNumber,
        processBinaryMessage
    } = useWebsocketBinaryMessageProcessor()


    const createAcknowledgment = (frameNumber: number): string => {
        return JSON.stringify({
            type: 'acknowledgment',
            frame_number: frameNumber
        });
    };
    const handleIncomingMessage = useCallback(async (event: MessageEvent, ws: WebSocket) => {
        const data = event.data;

        // Handle binary data (new format)
        if (data instanceof ArrayBuffer) {
            processBinaryMessage(data).then(frameNumber => {
                if (frameNumber !== null && ws.readyState === WebSocket.OPEN) {
                    ws.send(createAcknowledgment(frameNumber));
                }
            });
        }



        // Handle text/JSON data (for other message types)
        if (typeof data === 'string') {
            try {
                const parsedData = JSON.parse(data);

                // Handle other message types (logs, camera configs, etc.)
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
            } catch (e) {
                console.error(`Failed to parse websocket message: ${e}`);
            }
        }
    }, [dispatch, processBinaryMessage]);
    const connect = useCallback(() => {
        if (websocket && websocket.readyState !== WebSocket.CLOSED) {
            return;
        }
        if (connectAttempt >= MAX_RECONNECT_ATTEMPTS) {
            console.error(`Max reconnection attempts reached. Could not connect to ${wsUrl}`);
            return;
        }
        const ws = new WebSocket(wsUrl);
        ws.binaryType = 'arraybuffer';

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
