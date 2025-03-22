import {Box, Typography} from "@mui/material";
import React from "react";

interface CameraImageProps {
    cameraId: string;
    base64Image: string;
    showAnnotation: boolean;
}

export const CameraImage = ({cameraId, base64Image, showAnnotation}: CameraImageProps) => {
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
                src={`data:image/jpeg;base64,${base64Image}`}
                alt={`Camera ${cameraId}`}
                style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain',
                    display: 'block', // Remove any extra space below the image
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
