// hooks/use-frame-frameData.ts
import { useState, useEffect } from 'react';
import { frameRouter, type FrameMetadata } from '@/services/frames/frame-router';

/**
 * Hook to subscribe to frame frameData for all cameras
 */
export const useFrameData = () => {
    const [frameData, setFrameData] = useState<Map<string, FrameMetadata>>(
        () => frameRouter.getAllCameraMetadata()
    );

    useEffect(() => {
        const unsubscribe = frameRouter.subscribeToMetadataChanges(setFrameData);
        return unsubscribe;
    }, []);

    return {
        frameData,
        cameraIds: Array.from(frameData.keys()),
        cameraCount: frameData.size,
    };
};

/**
 * Hook to subscribe to frame data for a specific camera
 */
export const useCameraFrameData = (cameraId: string) => {
    const [frameData, setMetadata] = useState<FrameMetadata | undefined>(
        () => frameRouter.getCameraMetadata(cameraId)
    );

    useEffect(() => {
        const unsubscribe = frameRouter.subscribeToMetadataChanges((allMetadata) => {
            setMetadata(allMetadata.get(cameraId));
        });

        return unsubscribe;
    }, [cameraId]);

    return frameData;
};

/**
 * Hook to get FPS for a specific camera
 */
export const useCameraFPS = (cameraId: string) => {
    const frameData = useCameraFrameData(cameraId);
    return frameData?.fps ?? 0;
};

/**
 * Hook to get active camera count
 */
export const useActiveCameraCount = () => {
    const [count, setCount] = useState<number>(
        () => frameRouter.getAllCameraMetadata().size
    );

    useEffect(() => {
        const unsubscribe = frameRouter.subscribeToMetadataChanges((frameData) => {
            setCount(frameData.size);
        });

        return unsubscribe;
    }, []);

    return count;
};
