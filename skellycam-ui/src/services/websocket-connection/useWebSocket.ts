import {useCallback, useEffect, useState} from 'react';
import {z} from 'zod';
import {FrontendFramePayloadSchema, setLatestFrontendPayload} from '@/store/slices/latestFrontendPayloadSlice';
import {
    CurrentFramerate,
    setBackendFramerate,
    setFrontendFramerate
} from "@/store/slices/framerateTrackerSlice";
import {
    RecordingInfoSchema,
    setRecordingInfo
} from "@/store/slices/recordingInfoSlice";
import {CameraConfigsSchema} from "@/store/slices/cameras-slices/camera-types";
import {addLog, LogRecordSchema} from "@/store/slices/logRecordsSlice";
import {setConnectedCameraConfigs} from "@/store/slices/cameras-slices/connectedCameraConfigsSlice";
import {useAppDispatch} from "@/store/AppStateStore";

const MAX_RECONNECT_ATTEMPTS = 20;
export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);

    const dispatch = useAppDispatch();

    const handleIncomingMessage = useCallback((event: MessageEvent) => {
        const data = event.data;
        if (data instanceof Blob) {
            data.text().then(text => {
                parseAndValidateMessage(text);
            }).catch(error => {
                console.error('Error reading Blob data:', error);
            });
        } else if (typeof data === 'string') {
            parseAndValidateMessage(data);
        }
    }, []);

    const parseAndValidateMessage = useCallback((data: string) => {
        try {
            const parsedData = JSON.parse(data);
            try {
                const latestPayload = FrontendFramePayloadSchema.parse(parsedData);
                dispatch(setLatestFrontendPayload(latestPayload));
                if (latestPayload.frontend_framerate) {
                    dispatch(setFrontendFramerate(latestPayload.frontend_framerate as CurrentFramerate));
                }
                if (latestPayload.backend_framerate) {
                    dispatch(setBackendFramerate(latestPayload.backend_framerate as CurrentFramerate));
                }
                return;
            } catch (e) {
                // // Uncomment to log validation errors
                // if (e instanceof z.ZodError) {
                //     console.error('FrontendFramePayload validation failed:', {
                //         received: parsedData,
                //         errors: e.errors
                //     });
                // }
                if (!(e instanceof z.ZodError)) throw e; // Re-throw if not a validation error
            }
            try {
                const connectedCameraConfigs = CameraConfigsSchema.parse(parsedData);
                dispatch(setConnectedCameraConfigs(connectedCameraConfigs));
                return;
            } catch (e) {
                if (!(e instanceof z.ZodError)) throw e;
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
        disconnect
    };
};
