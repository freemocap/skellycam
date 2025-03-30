import {useCallback, useState} from 'react';
import {z} from 'zod';

export const JpegImagesSchema = z.record(
    z.string(),
    z.string()
);
export type JpegImages = z.infer<typeof JpegImagesSchema>;

export interface ImageUrlRecord {
    [cameraId: string]: string;
}

/**
 * Custom hook to manage the latest camera images from the frontend payload.
 * Simply converts base64 strings to data URLs without creating blobs.
 *
 * @returns Object containing latest data URLs for each camera
 */
export const useLatestImages = () => {
    const [latestImageUrls, setLatestImageUrls] = useState<ImageUrlRecord>({});

    const setLatestImages = useCallback((latestImages: JpegImages) => {
        const newImageUrls: ImageUrlRecord = {};

        // Create data URLs for all images in this batch
        Object.entries(latestImages).forEach(([cameraId, base64String]) => {
            // Skip processing if the string is empty
            if (!base64String) return;

            // Convert to data URL if needed
            newImageUrls[cameraId] = base64String.startsWith('data:')
                ? base64String
                : `data:image/jpeg;base64,${base64String}`;
        });

        // Update state with new URLs, preserving cameras not in this batch
        setLatestImageUrls(prev => ({
            ...prev,
            ...newImageUrls
        }));
    }, []);

    return {
        latestImageUrls,
        setLatestImages
    };
};
