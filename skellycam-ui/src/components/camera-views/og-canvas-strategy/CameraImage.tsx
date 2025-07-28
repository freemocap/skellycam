import { Box, Typography } from "@mui/material";
import React, { useRef, useMemo } from "react";
import { CameraImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

interface CameraImageProps {
    cameraImageData: CameraImageData;
    showAnnotation: boolean;
    cellWidth: number;
    cellHeight: number;
}

export const CameraImage = ({ cameraImageData, showAnnotation, cellWidth, cellHeight }: CameraImageProps) => {
    const { cameraId, imageBitmap, imageWidth, imageHeight, cameraIndex } = cameraImageData;
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Calculate the scaling factor to fit the image within the cell
    const { scale, scaledWidth, scaledHeight } = useMemo(() => {
        if (!cellWidth || !cellHeight || !imageWidth || !imageHeight) {
            return { scale: 1, scaledWidth: imageWidth, scaledHeight: imageHeight };
        }

        const imageAspectRatio = imageWidth / imageHeight;
        const cellAspectRatio = cellWidth / cellHeight;

        let scale: number;
        if (imageAspectRatio > cellAspectRatio) {
            // Image is wider than cell, scale by width
            scale = cellWidth / imageWidth;
        } else {
            // Image is taller than cell, scale by height
            scale = cellHeight / imageHeight;
        }

        // Calculate scaled dimensions
        const scaledWidth = imageWidth * scale;
        const scaledHeight = imageHeight * scale;

        return { scale, scaledWidth, scaledHeight };
    }, [imageWidth, imageHeight, cellWidth, cellHeight]);

    // Directly render the bitmap when the ref callback is called
    const setCanvasRef = (canvas: HTMLCanvasElement | null) => {
        if (canvas) {
            canvasRef.current = canvas;
        }
        if (canvas && imageBitmap) {
            const ctx = canvas.getContext('2d');
            if (ctx) {
                canvas.width = imageWidth;
                canvas.height = imageHeight;
                ctx.drawImage(imageBitmap, 0, 0);
            }
        }
    };

    // Also update the canvas whenever the component renders with a new imageBitmap
    if (canvasRef.current && imageBitmap) {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (ctx) {
            if (canvas.width !== imageWidth || canvas.height !== imageHeight) {
                canvas.width = imageWidth;
                canvas.height = imageHeight;
            }
            ctx.drawImage(imageBitmap, 0, 0);
        }
    }

    return (
        <Box
            key={cameraId}
            sx={{
                position: 'relative',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                width: '100%',
                height: '100%',
                overflow: 'hidden',
            }}
        >
            <canvas
                ref={setCanvasRef}
                style={{
                    width: `${scaledWidth}px`,
                    height: `${scaledHeight}px`,
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain',
                }}
            />
            {showAnnotation && (
                <Typography
                    variant="caption"
                    sx={{
                        position: "absolute",
                        bottom: 8,
                        left: 8,
                        color: "white",
                        backgroundColor: "rgba(0, 0, 0, 0.5)",
                        padding: "2px 4px",
                        borderRadius: "4px",
                        zIndex: 1,
                    }}
                >
                    Camera {cameraIndex}
                </Typography>
            )}
        </Box>
    );
};
