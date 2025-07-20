import { useCallback, useEffect, useRef, useState } from "react";
import { useAppDispatch } from "@/store/AppStateStore";
import { useWebsocketBinaryMessageProcessor } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

const MAX_RECONNECT_ATTEMPTS = 30;

export const useWebSocket = (wsUrl: string) => {
  const [isConnected, setIsConnected] = useState(false);
  const [websocket, setWebSocket] = useState<WebSocket | null>(null);
  const [connectAttempt, setConnectAttempt] = useState(0);
  const frameReceiptAcknowledgments = useRef(new Map<string, boolean>());
  const dispatch = useAppDispatch();

  const { processBinaryMessage, latestImageData, cameraIds } =
    useWebsocketBinaryMessageProcessor();

  const sendFrameAcknowledgment = useCallback(
    (cameraId: string, frameNumber: number) => {
      // Set this camera as acknowledged
      frameReceiptAcknowledgments.current.set(cameraId, true);

      // Check if we have acknowledgments for all known cameras
      const allCameraIds = cameraIds || [];

      // If we have no camera IDs yet (first frame), just acknowledge immediately
      if (allCameraIds.length === 0) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          websocket.send(
            JSON.stringify({
              type: "acknowledgment",
              frame_number: frameNumber,
            })
          );
        }
        return;
      }

      // Check if all cameras have acknowledged
      const allAcknowledged = allCameraIds.every(
        (id) => frameReceiptAcknowledgments.current.get(id) === true
      );

      if (allAcknowledged) {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          websocket.send(
            JSON.stringify({
              type: "acknowledgment",
              frame_number: frameNumber,
            })
          );

          // Reset acknowledgments for next frame
          allCameraIds.forEach((id) =>
            frameReceiptAcknowledgments.current.set(id, false)
          );
        }
      }
    },
    [websocket, cameraIds]
  );

  const handleIncomingMessage = useCallback(
    async (event: MessageEvent, ws: WebSocket) => {
      const data = event.data;

      // Handle binary data
      if (data instanceof ArrayBuffer) {
        // Reset acknowledgments for all known cameras
        const currentCameraIds = cameraIds || [];
        currentCameraIds.forEach((cameraId) =>
          frameReceiptAcknowledgments.current.set(cameraId, false)
        );
        await processBinaryMessage(data);
      }
    },
    [dispatch, processBinaryMessage, cameraIds, frameReceiptAcknowledgments]
  );
  const connect = useCallback(() => {
    if (websocket && websocket.readyState !== WebSocket.CLOSED) {
      return;
    }
    if (connectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      console.error(
        `Max reconnection attempts reached. Could not connect to ${wsUrl}`
      );
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
        `Connecting (attempt #${
          connectAttempt + 1
        } of ${MAX_RECONNECT_ATTEMPTS}) to websocket at url: ${wsUrl}`
      );
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
    latestImageData,
    sendFrameAcknowledgment,
  };
};
