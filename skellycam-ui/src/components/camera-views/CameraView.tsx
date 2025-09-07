import React, {useEffect, useRef} from 'react';
import {useAppSelector} from '@/store/hooks';
import {selectCameraFrameMetadata} from '@/store/slices/websocket/websocket-selectors';
import {frameRouter} from '@/services/frame-router';
import {websocketManager} from '@/services/websocket-manager';

interface CameraViewProps {
    cameraId: string;
    width: number;
    height: number;
}

export const CameraView: React.FC<CameraViewProps> = ({cameraId, width, height}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
    const frameNumberRef = useRef<number>(0);
    const frameMetadata = useAppSelector(state => selectCameraFrameMetadata(state, cameraId));

    // Setup canvas context once
    useEffect(() => {
        if (!canvasRef.current) return;

        ctxRef.current = canvasRef.current.getContext('2d', {
            alpha: false,
            desynchronized: true,
            willReadFrequently: false,
        });

        if (ctxRef.current) {
            ctxRef.current.imageSmoothingEnabled = false;
            ctxRef.current.imageSmoothingQuality = 'low';
        }
    }, []);

    // Subscribe to frame updates
    useEffect(() => {
        const unsubscribe = frameRouter.subscribe(
            cameraId,
            (bitmap, metadata) => {
                if (!ctxRef.current) return;

                // Draw immediately
                ctxRef.current.drawImage(bitmap, 0, 0, width, height);
                frameNumberRef.current = metadata.frameNumber;

                // Send acknowledgment
                websocketManager.acknowledgeFrameRendered(cameraId,metadata.frameNumber);
            }
        );

        return unsubscribe;
    }, [cameraId, width, height]);

    return (
        <div className="camera-view">
            <canvas
                ref={canvasRef}
                width={width}
                height={height}
                style={{
                    width: '100%',
                    height: 'auto',
                    imageRendering: 'pixelated',
                }}
            />
            {frameMetadata && (
                <div className="camera-stats">
                    Frame: {frameMetadata.frameNumber}
                </div>
            )}
        </div>
    );
};
