import {useCallback, useEffect, useState} from 'react';
import {useAppDispatch} from "@/store/AppStateStore";
import {useWebsocketBinaryMessageProcessor} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

const MAX_RECONNECT_ATTEMPTS = 30;


export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const dispatch = useAppDispatch();

    const {processBinaryMessage,
        latestImageData
    } = useWebsocketBinaryMessageProcessor();


    const createAcknowledgment = (frameNumber: number): string => {
        return JSON.stringify({
            type: 'acknowledgment',
            frame_number: frameNumber
        });
    };
    const handleIncomingMessage = useCallback(async (event: MessageEvent, ws: WebSocket) => {
        const data = event.data;

        // Handle binary data
        if (data instanceof ArrayBuffer) {
            const frameNumber = await processBinaryMessage(data);
            if (frameNumber !== null && ws.readyState === WebSocket.OPEN) {
                    ws.send(createAcknowledgment(frameNumber));
            }
        }
        //
        //
        // // Handle text/JSON data (for other message types)
        // if (typeof data === 'string') {
        //     try {
        //         const parsedData = JSON.parse(data);
        //         try {
        //             const incomingLogs = IncomingLogsSchema.parse(parsedData);
        //
        //             dispatch(addLogs(incomingLogs));
        //             return;
        //         } catch (e) {
        //             if (!(e instanceof z.ZodError)) throw e;
        //             console.error("Failed to parse log record:", e);
        //         }
        //
        //     } catch (e) {
        //         console.error(`Failed to parse websocket message: ${e}`);
        //     }
        // }
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
        latestImageData
    };
};
