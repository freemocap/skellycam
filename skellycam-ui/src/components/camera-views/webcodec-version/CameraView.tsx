import React, { useEffect, useRef, useCallback, useState } from 'react';
import {FrameMetadata, frameRouter, websocketService} from "@/services";

interface CameraViewProps {
    cameraId: string;
    width: number;
    height: number;
}

export const CameraView: React.FC<CameraViewProps> = ({ cameraId, width, height }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
    const renderingRef = useRef<boolean>(false);
    const lastRenderTimeRef = useRef<number>(0);

    // Local state for camera metadata
    const [metadata, setMetadata] = useState<FrameMetadata | undefined>(() =>
        frameRouter.getCameraMetadata(cameraId)
    );

    // Setup canvas context with optimal settings for high framerate
    useEffect(() => {
        if (!canvasRef.current) return;

        const ctx = canvasRef.current.getContext('2d', {
            alpha: false,                  // No transparency for better performance
            desynchronized: true,           // Bypass browser's compositor for lower latency
            willReadFrequently: false,      // We're only writing
            powerPreference: 'high-performance'  // Prefer discrete GPU if available
        }) as CanvasRenderingContext2D | null;

        if (ctx) {
            ctxRef.current = ctx;
            // Disable smoothing for pixel-perfect rendering and better performance
            ctx.imageSmoothingEnabled = false;
            ctx.imageSmoothingQuality = 'low';
        }

        return () => {
            ctxRef.current = null;
        };
    }, []);

    // Subscribe to metadata changes
    useEffect(() => {
        const unsubscribe = frameRouter.subscribeToMetadataChanges((allMetadata) => {
            const cameraMetadata = allMetadata.get(cameraId);
            setMetadata(cameraMetadata);
        });

        return unsubscribe;
    }, [cameraId]);

    // Optimized frame handler with frame dropping for smooth playback
    const handleFrame = useCallback((bitmap: ImageBitmap, frameMetadata: FrameMetadata) => {
        if (!ctxRef.current || renderingRef.current) {
            // Skip frame if still rendering previous one
            bitmap.close(); // Important: clean up skipped bitmaps
            return;
        }

        const now = performance.now();

        // Optional frame rate limiting
        // const minFrameTime = 1000 / 120; // Cap at 120 FPS
        // if (now - lastRenderTimeRef.current < minFrameTime) {
        //     bitmap.close();
        //     return;
        // }

        renderingRef.current = true;

        // Use requestAnimationFrame for synchronized rendering
        requestAnimationFrame(() => {
            if (ctxRef.current) {
                try {
                    // Draw the bitmap directly - fastest method
                    ctxRef.current.drawImage(bitmap, 0, 0, width, height);

                    lastRenderTimeRef.current = now;

                    // Send acknowledgment only for rendered frames
                    websocketService.acknowledgeFrameRendered(cameraId, frameMetadata.frameNumber);
                } catch (error) {
                    console.error(`Render error for camera ${cameraId}:`, error);
                } finally {
                    renderingRef.current = false;
                    // Bitmap cleanup is handled by frame-router
                }
            } else {
                renderingRef.current = false;
            }
        });
    }, [cameraId, width, height]);

    // Subscribe to frame updates
    useEffect(() => {
        const unsubscribe = frameRouter.subscribe(cameraId, handleFrame);

        return () => {
            unsubscribe();
            renderingRef.current = false;
        };
    }, [cameraId, handleFrame]);

    // Resize observer for responsive canvas
    useEffect(() => {
        if (!canvasRef.current) return;

        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const { width: containerWidth } = entry.contentRect;
                // Maintain aspect ratio
                const scale = containerWidth / width;
                const scaledHeight = height * scale;

                if (canvasRef.current) {
                    canvasRef.current.style.width = `${containerWidth}px`;
                    canvasRef.current.style.height = `${scaledHeight}px`;
                }
            }
        });

        const container = canvasRef.current.parentElement;
        if (container) {
            resizeObserver.observe(container);
        }

        return () => {
            resizeObserver.disconnect();
        };
    }, [width, height]);

    return (
        <div className="camera-view" style={{ position: 'relative', width: '100%' }}>
            <canvas
                ref={canvasRef}
                width={width}
                height={height}
                style={{
                    width: '100%',
                    height: 'auto',
                    display: 'block',
                    imageRendering: 'pixelated', // Prevents blurring when scaled
                }}
            />
            {metadata && (
                <div
                    className="camera-stats"
                    style={{
                        position: 'absolute',
                        top: 8,
                        left: 8,
                        background: 'rgba(0, 0, 0, 0.7)',
                        color: 'white',
                        padding: '4px 8px',
                        borderRadius: 4,
                        fontSize: '12px',
                        fontFamily: 'monospace',
                        pointerEvents: 'none',
                        userSelect: 'none',
                    }}
                >
                    <div>Camera: {cameraId}</div>
                    <div>Frame: {metadata.frameNumber}</div>
                    <div>FPS: {metadata.fps || 0}</div>
                    <div>Size: {metadata.width}x{metadata.height}</div>
                </div>
            )}
        </div>
    );
};
