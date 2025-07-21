import { useMemo } from 'react';
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

interface GridLayout {
    rows: number;
    columns: number;
}

/**
 * Hook to calculate optimal grid layout for camera views
 */
export function useCameraGridLayout(
    imageData: Record<string, CameraImageData>,
    containerWidth?: number,
    containerHeight?: number
): GridLayout {
    return useMemo(() => {
        const imageDataArray:CameraImageData[] = Object.values(imageData);
        if (!imageDataArray || imageDataArray.length === 0) return { rows: 1, columns: 1 };

        // For static grid without container dimensions, use simple layout
        if (!containerWidth || !containerHeight) {
            // Simple layout calculation based on number of cameras
            if (imageDataArray.length <= 1) return { rows: 1, columns: 1 };
            if (imageDataArray.length <= 2) return { rows: 1, columns: 2 };
            if (imageDataArray.length <= 4) return { rows: 2, columns: 2 };
            if (imageDataArray.length <= 6) return { rows: 2, columns: 3 };
            if (imageDataArray.length <= 9) return { rows: 3, columns: 3 };
            return {
                rows: Math.ceil(Math.sqrt(imageDataArray.length)),
                columns: Math.ceil(Math.sqrt(imageDataArray.length))
            };
        }

        // Advanced layout calculation for dynamic grid with container dimensions
        // Find the grid configuration that maximizes image size
        let bestLayout = { columns: 1, rows: 1, area: 0 };

        // Try different grid configurations
        for (let columns = 1; columns <= imageDataArray.length; columns++) {
            const rows = Math.ceil(imageDataArray.length / columns);

            // Calculate the area each image would get
            const cellWidth = containerWidth / columns;
            const cellHeight = containerHeight / rows;

            // Calculate minimum scaling factor across all images
            let minScale = Infinity;
            imageDataArray.forEach(image => {
                const aspectRatio = image.imageBitmap.width / image.imageBitmap.height;
                const scaleWidth = cellWidth / (aspectRatio * cellHeight);
                const scaleHeight = cellHeight / (aspectRatio === 0 ? 1 : cellWidth / aspectRatio);
                minScale = Math.min(minScale, Math.min(scaleWidth, scaleHeight));
            });

            // Calculate effective area
            const effectiveArea = minScale * (cellWidth * cellHeight);

            if (effectiveArea > bestLayout.area) {
                bestLayout = { columns, rows, area: effectiveArea };
            }
        }

        return { columns: bestLayout.columns, rows: bestLayout.rows };
    }, [imageData, containerWidth, containerHeight]);
}
