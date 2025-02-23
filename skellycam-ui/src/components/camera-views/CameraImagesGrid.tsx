import {Box, BoxProps} from "@mui/material";
import React from "react";
import {CameraImage} from "@/components/camera-views/CameraImage";

interface CameraImagesGridProps extends BoxProps { // Extend BoxProps
    images: { [cameraId: string]: string };
    showAnnotation: boolean;
}

export const CameraImagesGrid = ({ images, showAnnotation, sx }: CameraImagesGridProps) => {
    return (
        <Box
            sx={{
                display: "flex",
                flexDirection: "row",
                flexWrap: "wrap",
                // flexGrow: 1,
                justifyContent: "center",
                alignItems: "center",
                overflow: "hidden",
                    ...sx
            }}
        >
            {Object.entries(images).map(([cameraId, base64Image]) =>
                base64Image ? (
                    <CameraImage key={cameraId} cameraId={cameraId} base64Image={base64Image} showAnnotation={showAnnotation} />
                ) : null
            )}
        </Box>
    );
};
