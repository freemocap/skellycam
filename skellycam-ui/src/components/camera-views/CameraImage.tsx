// skellycam-ui/src/components/camera-views/CameraImage.tsx
import {Box, Typography} from "@mui/material";
import React from "react";

interface CameraImageProps {
    cameraId: string;
    imageUrl: string;
    showAnnotation: boolean;
}

export const CameraImage = ({cameraId, imageUrl, showAnnotation}: CameraImageProps) => {
    return (
        <Box
            key={cameraId}
            sx={{
                position: 'relative',
                width: '100%',
                height: '100%',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
            }}
        >
            <img
                src={imageUrl}
                alt={`Camera ${cameraId}`}
                style={{
                    width: '100%',         // Fill available width
                    height: '100%',        // Fill available height
                    objectFit: 'contain',  // Ensure the entire image is visible without cropping
                    display: 'block',      // Remove any extra space below the image
                }}
            />
            {showAnnotation && (
                <Typography
                    variant="caption"
                    sx={{
                        position: "absolute",
                        bottom: 30,
                        left: 8,
                        color: "white",
                        backgroundColor: "rgba(0, 0, 0, 0.75)",
                        padding: "2px 4px",
                        borderRadius: "4px"
                    }}
                >
                    Camera {cameraId}
                </Typography>
            )}
        </Box>
    );
};
