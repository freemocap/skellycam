import {Box, Typography} from "@mui/material";
import React from "react";
import {CameraImagesGrid} from "@/components/camera-views/CameraImagesGrid";
import {useLatestImagesContext} from "@/context/latest-images-context/LatestImagesContext";

export const CamerasView = () => {
    const {latestImageUrls} = useLatestImagesContext();
    const showAnnotation = true

    if (!latestImageUrls) {
        return (
            <Box sx={{p: 2}}>
                <Typography variant="h6" color="secondary">
                    Waiting for cameras to connect...
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{
            display: "flex",
            flexDirection: "column",
            height: "100%",
            width: "100%",
            overflow: "hidden"
        }}>
            <CameraImagesGrid
                latestImageUrls={latestImageUrls}
                showAnnotation={showAnnotation}
                sx={{flex: 1, minHeight: 0, height: "100%", width: "100%"}}
            />
        </Box>
    );
};
