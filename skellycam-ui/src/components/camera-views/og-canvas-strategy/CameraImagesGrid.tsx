import {Box} from "@mui/material";
import React from "react";
import {CameraImage} from "@/components/camera-views/og-canvas-strategy/CameraImage";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

export const CameraImagesGrid = () => {
    const {latestImageData} = useWebSocketContext();

    // Group images by orientation
    const portraitImages = Object.entries(latestImageData)
        .filter(([_, data]) => data && data.orientation === "portrait");

    const landscapeImages = Object.entries(latestImageData)
        .filter(([_, data]) => data && data.orientation === "landscape");

    const squareImages = Object.entries(latestImageData)
        .filter(([_, data]) => data && data.orientation === "square");

    return (
        <Box sx={{
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'row', // Main container as row to place orientation groups side by side
            gap: 1, // Add some spacing between orientation groups
        }}>
            {/* Portrait Images Container */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                flexWrap: 'wrap',
                flex: 1,
                borderRight: '1px solid #666',
            }}>
                {portraitImages.map(([cameraId, cameraImageData]) => (
                    <CameraImage
                        key={cameraId}
                        cameraImageData={cameraImageData}
                    />
                ))}
            </Box>

            {/* Landscape Images Container */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                flexWrap: 'wrap',
                flex: 1,
                borderRight: '1px solid #666',
            }}>
                {landscapeImages.map(([cameraId, cameraImageData]) => (
                    <CameraImage
                        key={cameraId}
                        cameraImageData={cameraImageData}
                    />
                ))}
            </Box>

            {/* Square Images Container */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                flexWrap: 'wrap',
                flex: 1,
            }}>
                {squareImages.map(([cameraId, cameraImageData]) => (
                    <CameraImage
                        key={cameraId}
                        cameraImageData={cameraImageData}
                    />
                ))}
            </Box>
        </Box>
    );
};
