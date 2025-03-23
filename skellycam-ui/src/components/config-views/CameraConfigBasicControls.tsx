import Grid from '@mui/material/Grid2';
import { TextField } from "@mui/material";
import * as React from "react";
import { CameraConfig } from "@/store/slices/cameraDevicesSlice";

interface CameraConfigBasicControlsProps {
    framerate: CameraConfig['framerate'];
    colorChannels: CameraConfig['color_channels'];
    onFramerateChange: (value: number) => void;
    onColorChannelsChange: (value: number) => void;
}

export const CameraConfigBasicControls: React.FC<CameraConfigBasicControlsProps> = ({
    framerate,
    colorChannels,
    onFramerateChange,
    onColorChannelsChange
}) => (
    <Grid container spacing={2}>
        <Grid size={6}>
            <TextField
                size="small"
                label="FPS"
                type="number"
                value={framerate}
                onChange={(e) => onFramerateChange(Number(e.target.value))}
                inputProps={{
                    min: 30,
                    max: 120,
                    step: 1
                }}
                fullWidth
            />
        </Grid>
        <Grid size={6}>
            <TextField
                size="small"
                label="Channels"
                type="number"
                value={colorChannels}
                onChange={(e) => onColorChannelsChange(Number(e.target.value))}
                inputProps={{
                    min: 1,
                    max: 4,
                    step: 1
                }}
                fullWidth
            />
        </Grid>
    </Grid>
);
