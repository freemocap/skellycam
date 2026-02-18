import React, { useEffect, useRef, memo } from 'react';
import { useServer } from '@/services/server/ServerContextProvider';
import { frontendColor, backendColor } from '@/components/framerate-viewer/FrameRateViewer';

interface CameraViewProps {
    cameraId: string;
    scale?: number;
    maxWidth?: boolean;
}

/**
 * CameraView component - renders a canvas for a single camera feed.
 * Wrapped in memo to prevent re-renders when props haven't changed.
 * FPS display uses direct DOM manipulation to avoid React re-renders.
 */
export const CameraView: React.FC<CameraViewProps> = memo(({ cameraId, scale, maxWidth }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const displayFpsRef = useRef<HTMLSpanElement>(null);
    const serverFpsRef = useRef<HTMLSpanElement>(null);
    const { setCanvasForCamera, getFps, getServerFps } = useServer();
    const animationFrameRef = useRef<number | null>(null);

    useEffect(() => {
        const canvas = canvasRef.current;

        if (canvas && cameraId) {
            console.log(`Setting up canvas for camera: ${cameraId}`);
            setCanvasForCamera(cameraId, canvas);
        }
    }, [cameraId, setCanvasForCamera]);

    // Update FPS displays using direct DOM manipulation to avoid React re-renders
    useEffect(() => {
        const updateFps = () => {
            const displayFps = getFps(cameraId);
            if (displayFpsRef.current) {
                displayFpsRef.current.textContent = displayFps !== null
                    ? `${displayFps.toFixed(1)}`
                    : '--';
            }
            const srvFps = getServerFps();
            if (serverFpsRef.current) {
                serverFpsRef.current.textContent = srvFps !== null
                    ? `${srvFps.toFixed(1)}`
                    : '--';
            }
            animationFrameRef.current = requestAnimationFrame(updateFps);
        };

        animationFrameRef.current = requestAnimationFrame(updateFps);

        return () => {
            if (animationFrameRef.current !== null) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, [cameraId, getFps, getServerFps]);

    const getCanvasStyle = (): React.CSSProperties => {
        if (maxWidth) {
            return { width: '100%', height: '100%', objectFit: 'contain' };
        }
        if (scale !== undefined && scale !== 1.0) {
            return { width: `${scale * 100}%`, height: `${scale * 100}%`, objectFit: 'contain' };
        }
        return { width: '100%', height: '100%', objectFit: 'contain' };
    };

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
                style={getCanvasStyle()}
            />
            <div
                style={{
                    position: 'absolute',
                    bottom: 8,
                    left: 8,
                    backgroundColor: 'rgba(0, 0, 0, 0.75)',
                    color: '#fff',
                    padding: '4px 8px',
                    borderRadius: 4,
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    lineHeight: 1.4,
                }}
            >
                <div>{cameraId}</div>
                <div style={{ fontSize: '10px', marginTop: '2px', display: 'flex', gap: '6px' }}>
                    <span style={{ color: frontendColor }}>
                        D:<span ref={displayFpsRef}>--</span>
                    </span>
                    <span style={{ color: backendColor }}>
                        S:<span ref={serverFpsRef}>--</span>
                    </span>
                    <span style={{ color: '#aaa' }}>fps</span>
                </div>
            </div>
        </div>
    );
}, (prevProps, nextProps) => {
    return prevProps.cameraId === nextProps.cameraId &&
        prevProps.scale === nextProps.scale &&
        prevProps.maxWidth === nextProps.maxWidth;
});

CameraView.displayName = 'CameraView';
