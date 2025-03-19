import {Box, ButtonGroup} from "@mui/material";
import {RecordButton} from "@/components/RecordButton";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";
import React from "react";

export default function CameraButtonsGroup() {
    return (
        <Box>
            <ConnectToCamerasButton/>
            <RecordButton/>
        </Box>
    );
}
