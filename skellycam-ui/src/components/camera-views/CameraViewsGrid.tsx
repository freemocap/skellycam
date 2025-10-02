import React, { useMemo } from "react";
import { Box } from "@mui/material";
import { CameraView } from "./CameraView";
import { useServer } from "@/services/server/ServerContextProvider";

export const CameraViewsGrid: React.FC = () => {
    const { connectedCameraIds } = useServer();

    const getGridColumns = (count: number): string => {
        if (count <= 1) return '1fr';
        if (count <= 2) return 'repeat(2, 1fr)';
        if (count <= 4) return 'repeat(2, 1fr)';
        if (count <= 6) return 'repeat(3, 1fr)';
        if (count <= 9) return 'repeat(3, 1fr)';
        return 'repeat(4, 1fr)';
    };

    // Memoize camera views - only recreates when camera IDs array changes
    const cameraViews = useMemo(() =>
            connectedCameraIds.map(cameraId => (
                <CameraView key={cameraId} cameraId={cameraId} />
            )),
        [connectedCameraIds]
    );

    const gridColumns = useMemo(
        () => getGridColumns(connectedCameraIds.length),
        [connectedCameraIds.length]
    );

    return (
        <Box sx={{
            height: '100%',
            width: '100%',
            display: 'grid',
            gridTemplateColumns: gridColumns,
            gap: 1,
            padding: 1,
            overflow: 'auto',
        }}>
            {cameraViews}

            {connectedCameraIds.length === 0 && (
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
