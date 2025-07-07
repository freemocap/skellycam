import { useMemo } from 'react';
import {ImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

interface GridLayout {
    rows: number;
    columns: number;
}

/**
 * Hook to calculate optimal grid layout for camera views
 */
export function useCameraGridLayout(
    imageData: ImageData[],
    containerWidth?: number,
    containerHeight?: number
): GridLayout {
    return useMemo(() => {
        if (!imageData || imageData.length === 0) return { rows: 1, columns: 1 };

        // For static grid without container dimensions, use simple layout
        if (!containerWidth || !containerHeight) {
            // Simple layout calculation based on number of cameras
            if (imageData.length <= 1) return { rows: 1, columns: 1 };
            if (imageData.length <= 2) return { rows: 1, columns: 2 };
            if (imageData.length <= 4) return { rows: 2, columns: 2 };
            if (imageData.length <= 6) return { rows: 2, columns: 3 };
            if (imageData.length <= 9) return { rows: 3, columns: 3 };
            return {
                rows: Math.ceil(Math.sqrt(imageData.length)),
                columns: Math.ceil(Math.sqrt(imageData.length))
            };
        }

        // Advanced layout calculation for dynamic grid with container dimensions
        // Find the grid configuration that maximizes image size
        let bestLayout = { columns: 1, rows: 1, area: 0 };

        // Try different grid configurations
        for (let columns = 1; columns <= imageData.length; columns++) {
            const rows = Math.ceil(imageData.length / columns);

            // Calculate the area each image would get
            const cellWidth = containerWidth / columns;
            const cellHeight = containerHeight / rows;

            // Calculate minimum scaling factor across all images
            let minScale = Infinity;
            imageData.forEach(image => {
                const aspectRatio = image.imageWidth / image.imageHeight;
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
