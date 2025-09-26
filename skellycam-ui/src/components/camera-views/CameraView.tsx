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



    const handleFrame = useCallback((frame: ParsedFrame) => {

        requestAnimationFrame(() => {
            if (ctxRef.current) {
                try {
                    ctxRef.current.drawImage(frame.jpegData, 0, 0, width, height);

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
