// skellycam-ui/src/components/camera-views/CameraImagesGrid.tsx
import {Box, BoxProps} from "@mui/material";
import React, {useEffect, useRef, useState} from "react";
import {CameraImage} from "@/components/camera-views/CameraImage";

interface CameraImagesGridProps extends BoxProps {
    latestImageUrls: { [cameraId: string]: string };
    showAnnotation: boolean;
}

export const CameraImagesGrid = ({ latestImageUrls, showAnnotation, sx }: CameraImagesGridProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [gridDimensions, setGridDimensions] = useState({ columns: 1, rows: 1 });
    const imageCount = Object.keys(latestImageUrls).length;

    useEffect(() => {
        const updateLayout = () => {
            if (!containerRef.current) return;

            const container = containerRef.current;
            const containerWidth = container.clientWidth;
            const containerHeight = container.clientHeight;
            const aspectRatio = containerWidth / containerHeight;

            // Try different column counts to find the best fit
            let bestColumns = 1;
            let bestRows = imageCount;
            let bestRatio = Math.abs(aspectRatio - (bestColumns / bestRows));

            // Test different column counts to find the arrangement
            // that best matches the container's aspect ratio
            for (let cols = 1; cols <= imageCount; cols++) {
                const rows = Math.ceil(imageCount / cols);
                const ratio = Math.abs(aspectRatio - (cols / rows));

                // Update if this arrangement is better
                if (ratio < bestRatio) {
                    bestRatio = ratio;
                    bestColumns = cols;
                    bestRows = rows;
                }
            }

            setGridDimensions({
                columns: bestColumns,
                rows: bestRows
            });
        };

        updateLayout();

        // Update layout on resize
        const resizeObserver = new ResizeObserver(updateLayout);
        if (containerRef.current) {
            resizeObserver.observe(containerRef.current);
        }

        return () => resizeObserver.disconnect();
    }, [imageCount]);

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
                overflow: "hidden", // Prevent scrolling
                ...sx
            }}
        >
            {Object.entries(latestImageUrls).map(([cameraId, imageUrl]) =>
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
