import {useCallback, useEffect, useRef, useState} from "react";
import {useAppDispatch} from "@/store/AppStateStore";
import {useWebsocketBinaryMessageProcessor} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

export interface CameraDisplaySize {
    width: number;
    height: number;
}

export interface FrameRenderAcknowledgment {
    frameNumber: number;
    displayImageSizes: Record<string, CameraDisplaySize>;
}

export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const dispatch = useAppDispatch();
    const latestFrameNumber = useRef<number>(-1);
    const cameraRenderAcknowledgment = useRef<Record<string, number>>({});
    const latestFrameRenderAcknowledgment = useRef<FrameRenderAcknowledgment>({
        frameNumber: -1,
        displayImageSizes: {}
    });
    const {processBinaryMessage, latestImageData} =
        useWebsocketBinaryMessageProcessor();


    const sendFrameAcknowledgment = useCallback(
        (cameraId: string, frameNumber: number, imageDisplayWidth: number, imageDisplayHeight: number) => {
            cameraRenderAcknowledgment.current[cameraId] = frameNumber
            latestFrameNumber.current = Math.max(latestFrameNumber.current, frameNumber);
            const allCamerasAcknowledged = Object.values(cameraRenderAcknowledgment.current).every(
                (acknowledgedFrame) => acknowledgedFrame >= latestFrameNumber.current
            );
            latestFrameRenderAcknowledgment.current = {
                frameNumber: Math.max(latestFrameRenderAcknowledgment.current.frameNumber, frameNumber),
                displayImageSizes: {
                    ...latestFrameRenderAcknowledgment.current.displayImageSizes,
                    [cameraId]: {
                        width: imageDisplayWidth,
                        height: imageDisplayHeight
                    }
                }
            }
            if (allCamerasAcknowledged) {
                console.log(`All cameras acknowledged frame ${latestFrameRenderAcknowledgment.current.frameNumber}, sending acknowledgment to server ${JSON.stringify(latestFrameRenderAcknowledgment.current, null, 2)}`);
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(
                        JSON.stringify(latestFrameRenderAcknowledgment.current)
                    )
                }
            }
        }, [websocket, cameraRenderAcknowledgment, latestFrameNumber]);


    const handleIncomingMessage = useCallback(
        async (event: MessageEvent, ws: WebSocket) => {
            const data = event.data;

            // Handle binary data
            if (data instanceof ArrayBuffer) {
                const frameNumber = await processBinaryMessage(data);
                if (frameNumber !== null) {
                    latestFrameNumber.current = frameNumber
                }
            } else if (typeof data === "string") {
                if (data == 'ping') {
                    console.log("Received ping message, sending pong response");
                    ws.send("pong");
                    return;
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
            handleIncomingMessage(event, ws);
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
        sendFrameAcknowledgment,
    };
};
