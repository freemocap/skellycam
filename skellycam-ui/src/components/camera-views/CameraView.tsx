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
    const fpsDisplayRef = useRef<HTMLSpanElement>(null);
    const { setCanvasForCamera, getFps } = useServer();
    const hasSetCanvas = useRef<boolean>(false);
    const animationFrameRef = useRef<number | null>(null);

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

    // Update FPS display using direct DOM manipulation to avoid React re-renders
    useEffect(() => {
        const updateFps = () => {
            const fps = getFps(cameraId);
            if (fpsDisplayRef.current && fps !== null) {
                fpsDisplayRef.current.textContent = `${fps.toFixed(1)} FPS`;
            }
            animationFrameRef.current = requestAnimationFrame(updateFps);
        };

        animationFrameRef.current = requestAnimationFrame(updateFps);

        return () => {
            if (animationFrameRef.current !== null) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [cameraId, getFps]);

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
                <div>{cameraId}</div>
                <div style={{ fontSize: '10px', marginTop: '2px', color: '#0f0' }}>
                    <span ref={fpsDisplayRef}>-- FPS</span>
                </div>
            </div>
        </div>
    );
}, (prevProps, nextProps) => {
    // Custom comparison: only re-render if cameraId changes
    return prevProps.cameraId === nextProps.cameraId;
});

CameraView.displayName = 'CameraView';
