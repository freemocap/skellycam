import {Box} from "@mui/material";
import React, {useEffect, useState} from "react";
import {useWebSocketContext} from "@/services/websocket-connection/WebSocketContext";
import {CameraImagesGrid} from "@/components/camera-views/CameraImagesGrid";
import {RecordButton} from "@/components/RecordButton";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";
import CameraButtonsGroup from "./CameraButtonsGroup";
import {useAppSelector} from "@/store/hooks";


export const CamerasView = () => {
    const [showAnnotation, setShowAnnotation] = useState(true);
    const latestImages = useAppSelector(state => state.frontendPayload.latestImages);
    const toggleAnnotation = () => {
        setShowAnnotation(prev => !prev);
    };

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
