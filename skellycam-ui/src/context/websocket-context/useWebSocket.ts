import {useCallback, useEffect, useRef, useState} from "react";
import {useAppDispatch} from "@/store/AppStateStore";
import {
    FrameRenderAcknowledgment,
    useWebsocketBinaryMessageProcessor
} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";


export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const dispatch = useAppDispatch();
    const {
        processBinaryMessage,
        latestImageData,
        registerCameraViewTexture
    } = useWebsocketBinaryMessageProcessor();




    const handleIncomingMessage = useCallback(
        async (event: MessageEvent, ws: WebSocket) => {
            const data = event.data;

            // Handle binary data
            if (data instanceof ArrayBuffer) {
                const frameRenderAcknowledgment = await processBinaryMessage(data);
                if (frameRenderAcknowledgment) {
                    ws.send(
                        JSON.stringify(frameRenderAcknowledgment)
                    )
                }
            } else if (typeof data === "string") {
                if (data == 'ping') {
                    console.log("Received ping message, sending pong response");
                    ws.send("pong");
                }
                try {
                    const message = JSON.parse(data);
                    console.log("Received JSON message:", JSON.stringify(message, null, 2));
                } catch (error) {
                    console.log("Received non-JSON string data:", data);
                }
            } else {
                console.warn("Received unsupported message type:", typeof data);
            }
        },
        [dispatch, processBinaryMessage]
    );
    const connect = useCallback(() => {
        if (websocket && websocket.readyState !== WebSocket.CLOSED) {
            return;
        }

        const ws = new WebSocket(wsUrl);
        ws.binaryType = "arraybuffer";

        ws.onopen = () => {
            setIsConnected(true);
            setConnectAttempt(0);
            ws.send("Hello from the Skellycam Frontend💀📸👋");
            console.log(`Websocket is connected to url: ${wsUrl}`);
        };

        ws.onclose = () => {
            setIsConnected(false);
            setConnectAttempt((prev) => prev + 1);
        };

        ws.onmessage = (event) => {
            handleIncomingMessage(event, ws).then(
                () => {}
            ).catch((error) => {
                console.error("Error processing incoming message:", error);
            }
            );
        };

        ws.onerror = (error) => {
            console.error("Websocket error:", error);
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
            console.log(
                `Connecting  to websocket at url: ${wsUrl} (attempt #${connectAttempt + 1})`
            );
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 10000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };
    }, [connect, connectAttempt, wsUrl]);

    return {
        isConnected,
        connect,
        disconnect,
        latestImageData,
        registerCameraViewTexture,
    };
};
