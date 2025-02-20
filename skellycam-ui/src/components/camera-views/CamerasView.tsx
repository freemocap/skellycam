import {Box} from "@mui/material";
import React, {useEffect, useState} from "react";
import {useWebSocketContext} from "@/context/WebSocketContext";
import {CameraImagesGrid} from "@/components/camera-views/CameraImagesGrid";


export const CamerasView = () => {
    const {latestImages} = useWebSocketContext();
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
            display: "flex",
            flexDirection: "column",
            height: "100%",
            width: "100%",
            overflow: "hidden"

        }}>
            cameras
            {latestImages && (
                <CameraImagesGrid
                    images={latestImages}
                    showAnnotation={showAnnotation}
                    sx={{flex: 1, minHeight: 0}} // Allows grid to shrink
                />
            )}
        </Box>
    );
};
