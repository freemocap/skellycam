import { Box } from "@mui/material";
import React, {useEffect, useMemo, useRef, useState} from "react";
import {CameraImage} from "@/components/camera-views/og-canvas-strategy/CameraImage";
import { CameraImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {useCameraGridLayout} from "@/hooks/useCameraGridLayout";

interface CameraImagesGridProps {
    imageData:  Record<string, CameraImageData>;
    showAnnotation: boolean;
}

export const CameraImagesGrid = ({ imageData, showAnnotation }: CameraImagesGridProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerDimensions, setContainerDimensions] = useState<{ width: number; height: number } | null>(null);
    // Update container dimensions when the component mounts or resizes
    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                setContainerDimensions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight
                });
            }
        };

        updateDimensions();

        // Set up resize observer to handle container size changes
        const resizeObserver = new ResizeObserver(updateDimensions);
        if (containerRef.current) {
            resizeObserver.observe(containerRef.current);
        }

        return () => {
            resizeObserver.disconnect();
        };
    }, []);
    // Calculate the optimal grid layout
    const { rows, columns } = useCameraGridLayout(
        imageData,
        containerDimensions?.width,
        containerDimensions?.height
    );

    // Calculate cell dimensions
    const cellWidth = containerDimensions ? containerDimensions.width / columns : 0;
    const cellHeight = containerDimensions ? containerDimensions.height / rows : 0;
    return (
        <Box
            ref={containerRef}
            sx={{
                height: '100%',
                width: '100%',
                display: "grid",
                gridTemplateColumns: `repeat(${columns}, 1fr)`,
                gridTemplateRows: `repeat(${rows}, 1fr)`,
                gap: 1,
            }}
        >
            {Object.entries(imageData).map(([cameraId, cameraImageData]) =>
                cameraImageData ? (
                    <CameraImage
                        key={cameraId}
                        cameraImageData={cameraImageData}
                        showAnnotation={showAnnotation}
                        cellWidth={cellWidth}
                        cellHeight={cellHeight}
                    />
                ) : null
            )}
        </Box>
    );
};
