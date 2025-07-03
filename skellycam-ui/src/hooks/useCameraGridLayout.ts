import { useMemo } from 'react';

// Represents image data for a camera
export interface ProcessedImageInfo {
    cameraId: string;
    aspectRatio: number; // width / height
    cameraIndex: number; // Added camera index for sorting
}

interface GridLayout {
    rows: number;
    cols: number;
}

/**
 * Hook to calculate optimal grid layout for camera views
 */
export function useCameraGridLayout(
    images: ProcessedImageInfo[],
    containerWidth?: number,
    containerHeight?: number
): GridLayout {
    return useMemo(() => {
        if (images.length === 0) return { rows: 1, cols: 1 };

        // For static grid without container dimensions, use simple layout
        if (!containerWidth || !containerHeight) {
            // Simple layout calculation based on number of cameras
            if (images.length <= 1) return { rows: 1, cols: 1 };
            if (images.length <= 2) return { rows: 1, cols: 2 };
            if (images.length <= 4) return { rows: 2, cols: 2 };
            if (images.length <= 6) return { rows: 2, cols: 3 };
            if (images.length <= 9) return { rows: 3, cols: 3 };
            return { 
                rows: Math.ceil(Math.sqrt(images.length)), 
                cols: Math.ceil(Math.sqrt(images.length)) 
            };
        }

        // Advanced layout calculation for dynamic grid with container dimensions
        // Find the grid configuration that maximizes image size
        let bestLayout = { cols: 1, rows: 1, area: 0 };

        // Try different grid configurations
        for (let cols = 1; cols <= images.length; cols++) {
            const rows = Math.ceil(images.length / cols);

            // Calculate the area each image would get
            const cellWidth = containerWidth / cols;
            const cellHeight = containerHeight / rows;

            // Calculate minimum scaling factor across all images
            let minScale = Infinity;
            images.forEach(image => {
                const scaleWidth = cellWidth / (image.aspectRatio * cellHeight);
                const scaleHeight = cellHeight / (image.aspectRatio === 0 ? 1 : cellWidth / image.aspectRatio);
                minScale = Math.min(minScale, Math.min(scaleWidth, scaleHeight));
            });

            // Calculate effective area
            const effectiveArea = minScale * (cellWidth * cellHeight);

            if (effectiveArea > bestLayout.area) {
                bestLayout = { cols, rows, area: effectiveArea };
            }
        }

        return { cols: bestLayout.cols, rows: bestLayout.rows };
    }, [images, containerWidth, containerHeight]);
}

/**
 * Helper function to sort camera images by camera index
 */
export function sortCamerasByIndex(
    imageBitmaps: Record<string, ImageBitmap>,
    cameraConfigs: Record<string, any>
): ProcessedImageInfo[] {
    // Create array of image info objects
    const images: ProcessedImageInfo[] = Object.entries(imageBitmaps).map(([cameraId, bitmap]) => ({
        cameraId,
        aspectRatio: bitmap.width / bitmap.height,
        cameraIndex: cameraConfigs[cameraId]?.camera_index ?? Number.MAX_SAFE_INTEGER
    }));

    // Sort by camera index
    return images.sort((a, b) => a.cameraIndex - b.cameraIndex);
}