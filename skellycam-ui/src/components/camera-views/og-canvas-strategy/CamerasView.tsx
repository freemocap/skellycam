import { Box, Button } from "@mui/material";
import React, { useState, useEffect } from "react";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {CameraImagesGrid} from "@/components/camera-views/og-canvas-strategy/CameraImagesGrid";


export const CamerasView = () => {
    const {latestImageData} = useWebSocketContext();
    const [showAnnotation, setShowAnnotation] = useState(true);
    const toggleAnnotation = () => {
        setShowAnnotation(prev => !prev);
    };

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'a') {
                toggleAnnotation();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
        };
    }, []);

    return (
        <Box sx={{
            height: '100%',
            width: '100%',
            display: 'flex',
        }}>
            {latestImageData && (
                <CameraImagesGrid imageData={latestImageData} showAnnotation={showAnnotation} />
            )}
        </Box>
    );
};
