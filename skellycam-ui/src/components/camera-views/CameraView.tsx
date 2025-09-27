import React, { useEffect, useRef } from 'react';
import { useWebSocket } from '@/services/websocket/WebsocketContextProvider';

interface CameraViewProps {
    cameraId: string;
}

export const CameraView: React.FC<CameraViewProps> = ({ cameraId }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const { setCanvasForCamera } = useWebSocket();

    useEffect(() => {
        if (canvasRef.current && cameraId) {
            // Set up the canvas for this camera
            setCanvasForCamera(cameraId, canvasRef.current);
        }
    }, [cameraId, setCanvasForCamera]);

    return (
        <canvas
            ref={canvasRef}
            width={640}
            height={480}
            style={{ border: '1px solid #ccc' }}
        />
    );
};
