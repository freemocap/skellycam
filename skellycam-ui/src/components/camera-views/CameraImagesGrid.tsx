// skellycam-ui/src/components/camera-views/CameraImagesGrid.tsx
import {Box, BoxProps} from "@mui/material";
import React, {useEffect, useRef, useState, useMemo} from "react";
import {CameraImage} from "@/components/camera-views/CameraImage";

interface CameraImagesGridProps extends BoxProps {
    latestImageUrls: { [cameraId: string]: string };
    showAnnotation: boolean;
}

interface GridDimensions {
    columns: number;
    rows: number;
}

export const CameraImagesGrid = ({ latestImageUrls, showAnnotation, sx }: CameraImagesGridProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
    const imageCount = Object.keys(latestImageUrls).length;

    // Cache the calculation results for improved performance
    const gridDimensions = useMemo(() =>
        findOptimalGridLayout(imageCount, containerSize.width, containerSize.height),
        [imageCount, containerSize.width, containerSize.height]
    );

    useEffect(() => {
        if (!containerRef.current) return;

        const updateContainerSize = () => {
            if (!containerRef.current) return;

            const container = containerRef.current;
            setContainerSize({
                width: container.clientWidth,
                height: container.clientHeight
            });
        };

        updateContainerSize();

        // Use ResizeObserver to detect size changes
        const resizeObserver = new ResizeObserver(entries => {
            // Only update when size changes significantly (reduce unnecessary calculations)
            const entry = entries[0];
            if (!entry) return;

            // Get the new size
            const { width, height } = entry.contentRect;

            // Update only if the size has changed by more than 10px
            setContainerSize(prev => {
                if (Math.abs(prev.width - width) > 10 || Math.abs(prev.height - height) > 10) {
                    return { width, height };
                }
                return prev;
            });
        });

        if (containerRef.current) {
            resizeObserver.observe(containerRef.current);
        }

        return () => resizeObserver.disconnect();
    }, []);

    return (
        <Box
            ref={containerRef}
            sx={{
                width: "100%",
                height: "100%",
                display: "grid",
                gridTemplateColumns: `repeat(${gridDimensions.columns}, 1fr)`,
                gridTemplateRows: `repeat(${gridDimensions.rows}, 1fr)`,
                gap: 1,
                padding: 1,
                overflow: "hidden",
                ...sx
            }}
        >
            {Object.entries(latestImageUrls).map(([cameraId, imageUrl], index) =>
                imageUrl ? (
                    <Box
                        key={cameraId}
                        sx={{
                            width: "100%",
                            height: "100%",
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            overflow: "hidden",
                            gridColumn: `${(index % gridDimensions.columns) + 1}`,
                            gridRow: `${Math.floor(index / gridDimensions.columns) + 1}`,
                        }}
                    >
                        <CameraImage
                            cameraId={cameraId}
                            imageUrl={imageUrl}
                            showAnnotation={showAnnotation}
                        />
                    </Box>
                ) : null
            )}
        </Box>
    );
};

// This is a separate function to keep the logic clean and testable
function findOptimalGridLayout(count: number, width: number, height: number): GridDimensions {
    if (count <= 0) return { columns: 1, rows: 1 };
    if (count === 1) return { columns: 1, rows: 1 };

    // Special cases for common camera counts - hardcoded optimal layouts
    if (count === 2) return width > height ? { columns: 2, rows: 1 } : { columns: 1, rows: 2 };
    if (count === 3) return width > height ? { columns: 3, rows: 1 } : { columns: 1, rows: 3 };
    if (count === 4) return { columns: 2, rows: 2 };

    const containerRatio = width / height;

    // Find the grid arrangement that:
    // 1. Minimizes wasted cells
    // 2. Keeps a ratio close to the container's ratio

    let bestColumns = 1;
    let bestRows = count;
    let bestWaste = count; // Worst case: all cells wasted
    let bestRatioDiff = Math.abs(containerRatio - bestColumns / bestRows);

    // Only check reasonable column counts
    const maxColumns = Math.ceil(Math.sqrt(count) * 2);

    for (let cols = 1; cols <= maxColumns; cols++) {
        const rows = Math.ceil(count / cols);
        const totalCells = cols * rows;
        const waste = totalCells - count;
        const ratioDiff = Math.abs(containerRatio - cols / rows);

        // Prioritize minimum waste, then closest aspect ratio
        if (waste < bestWaste || (waste === bestWaste && ratioDiff < bestRatioDiff)) {
            bestWaste = waste;
            bestRatioDiff = ratioDiff;
            bestColumns = cols;
            bestRows = rows;
        }
    }

    return { columns: bestColumns, rows: bestRows };
}
