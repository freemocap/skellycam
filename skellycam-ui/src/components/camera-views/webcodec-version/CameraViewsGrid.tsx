import React, { useState, useEffect } from "react";
import { Box } from "@mui/material";
import { CameraView } from "./CameraView";
import { frameRouter, type FrameMetadata } from "@/services/frames/frame-router";

export const CameraViewsGrid: React.FC = () => {
    const [cameraMetadata, setCameraMetadata] = useState<Map<string, FrameMetadata>>(
        () => frameRouter.getAllCameraMetadata()
    );

    // Subscribe to metadata changes
    useEffect(() => {
        const unsubscribe = frameRouter.subscribeToMetadataChanges((metadata) => {
            setCameraMetadata(metadata);
        });

        return unsubscribe;
    }, []);

    // Get camera IDs from the metadata
    const cameraIds = Array.from(cameraMetadata.keys());

    // Default dimensions - you may want to make these configurable
    const defaultWidth = 640;
    const defaultHeight = 480;

    // Calculate optimal grid layout based on number of cameras
    const getGridColumns = (count: number): string => {
        if (count <= 1) return '1fr';
        if (count <= 2) return 'repeat(2, 1fr)';
        if (count <= 4) return 'repeat(2, 1fr)';
        if (count <= 6) return 'repeat(3, 1fr)';
        if (count <= 9) return 'repeat(3, 1fr)';
        return 'repeat(4, 1fr)';
    };

    return (
        <Box sx={{
            height: '100%',
            width: '100%',
            display: 'grid',
            gridTemplateColumns: getGridColumns(cameraIds.length),
            gap: 1,
            padding: 1,
            overflow: 'auto',
        }}>
            {cameraIds.map((cameraId) => {
                const metadata = cameraMetadata.get(cameraId);

                if (!metadata) return null;

                return (
                    <Box
                        key={cameraId}
                        sx={{
                            position: 'relative',
                            width: '100%',
                            height: 'fit-content',
                            backgroundColor: 'background.paper',
                            borderRadius: 1,
                            overflow: 'hidden',
                            boxShadow: 1,
                        }}
                    >
                        <CameraView
                            cameraId={cameraId}
                            width={metadata.width || defaultWidth}
                            height={metadata.height || defaultHeight}
                        />
                    </Box>
                );
            })}

            {cameraIds.length === 0 && (
                <Box
                    sx={{
                        gridColumn: '1 / -1',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'text.secondary',
                        fontSize: '1.2rem',
                        padding: 4,
                        textAlign: 'center',
                    }}
                >
                    <div>
                        <div>No cameras connected</div>
                        <div style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
                            Waiting for camera streams...
                        </div>
                    </div>
                </Box>
            )}
        </Box>
    );
};
