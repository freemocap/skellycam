import {Box} from "@mui/material";
import React  from "react";
import {CameraImagesGrid} from "@/components/camera-views/CameraImagesGrid";

import {useAppSelector} from "@/store/AppStateStore";


export const CamerasView = () => {
    const latestImages = useAppSelector(state => state.latestPayload.latestImages);
    const showAnnotation = true
    if (!latestImages) {
        return (
            <Box sx={{p: 2}}>
                Waiting for camera feed...
            </Box>
        );
    }

    return (
        <Box sx={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            height: "100%",
            width: "100%",
            overflow: "hidden"

        }}>
            cameras
            {latestImages && (
                <CameraImagesGrid
                    images={latestImages}
                    showAnnotation={showAnnotation}
                    sx={{flex: 1, minHeight: 0, height: "100%", width: "100%"}}
                />
            )}


        </Box>
    );
};
