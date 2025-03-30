import {useCallback, useEffect, useState} from 'react';
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
 * Custom hook to efficiently manage the latest camera images from the frontend payload.
 * Converts base64 JPEG images to blob URLs and handles proper cleanup to prevent memory leaks.
 *
 * @returns Object containing latest blob URLs for each camera
 */

export const useLatestImages = () => {
    const [latestImageUrls, setLatestImageUrls] = useState<ImageUrlRecord>({});

    const setLatestImages = useCallback((latestImages: JpegImages) => {

        // Track the URLs we're going to create in this batch
        const newBlobUrls: ImageUrlRecord = {};

        // Process new or updating images
        const promises = Object.entries(latestImages).map(async ([cameraId, base64String]) => {
            try {
                // Create data URL if needed
                const dataUrl = base64String.startsWith('data:')
                    ? base64String
                    : `data:image/jpeg;base64,${base64String}`;

                // Convert to blob efficiently
                const response = await fetch(dataUrl);
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);

                return {cameraId, url};
            } catch (error) {
                console.error(`Error processing image for camera ${cameraId}:`, error);
                return {cameraId, url: ''};
            }
        });


        // Update state with new URLs once all promises are settled
        Promise.all(promises).then(results => {
            // Get the old URLs that need to be revoked
            const oldUrls = {...latestImageUrls};

            results.forEach(({cameraId, url}) => {
                if (url) {
                    newBlobUrls[cameraId] = url;
                }
            });

            // Update state with new URLs
            setLatestImageUrls(prev => {
                // Identify URLs to revoke (URLs being replaced or removed)
                Object.keys(oldUrls).forEach(cameraId => {
                    if (newBlobUrls[cameraId] && oldUrls[cameraId] !== newBlobUrls[cameraId]) {
                        // If this camera has a new URL, revoke the old one
                        URL.revokeObjectURL(oldUrls[cameraId]);
                    } else if (!newBlobUrls[cameraId]) {
                        // Keep URLs for cameras not in the new batch
                        newBlobUrls[cameraId] = oldUrls[cameraId];
                    }
                });

                return newBlobUrls;
            });
        });
    }, [latestImageUrls]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            Object.values(latestImageUrls).forEach(url => {
                URL.revokeObjectURL(url);
            });
        };
    }, []);

    return {
        latestImageUrls,
        setLatestImages
    };
};
