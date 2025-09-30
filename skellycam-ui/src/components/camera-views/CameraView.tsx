import React, { useEffect, useRef, memo } from 'react';
import { useServer } from '@/services/server/ServerContextProvider';

interface CameraViewProps {
    cameraId: string;
}

/**
 * CameraView component - renders a canvas for a single camera feed.
 * Wrapped in memo to prevent re-renders when props haven't changed.
 * This is critical for performance when multiple cameras are streaming.
 */
export const CameraView: React.FC<CameraViewProps> = memo(({ cameraId }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const { setCanvasForCamera } = useServer();
    const hasSetCanvas = useRef<boolean>(false);

    useEffect(() => {
        const canvas = canvasRef.current;

        if (canvas && cameraId && !hasSetCanvas.current) {
            console.log(`Setting up canvas for camera: ${cameraId}`);
            setCanvasForCamera(cameraId, canvas);
            hasSetCanvas.current = true;
        }

        // Cleanup: The ServerContext will handle worker termination
        // when the camera stops sending frames (via timeout mechanism)
        return () => {
            hasSetCanvas.current = false;
        };
    }, [cameraId, setCanvasForCamera]);

    return (
        <div
            style={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: '#000',
                position: 'relative',
                overflow: 'hidden'
            }}
        >
            <canvas
                ref={canvasRef}
                width={640}
                height={480}
                style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                }}
            />
            <div
                style={{
                    position: 'absolute',
                    bottom: 8,
                    left: 8,
                    backgroundColor: 'rgba(0, 0, 0, 0.7)',
                    color: '#fff',
                    padding: '4px 8px',
                    borderRadius: 4,
                    fontSize: '12px',
                    fontFamily: 'monospace'
                }}
            >
                {cameraId}
            </div>
        </div>
    );
}, (prevProps, nextProps) => {
    // Custom comparison: only re-render if cameraId changes
    return prevProps.cameraId === nextProps.cameraId;
});

CameraView.displayName = 'CameraView';
