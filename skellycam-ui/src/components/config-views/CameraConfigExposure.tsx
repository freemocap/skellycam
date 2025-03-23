import { FormControl, InputLabel, MenuItem, Select, TextField } from "@mui/material";
import Grid from '@mui/material/Grid2';
import * as React from "react";
import { CameraConfig } from "@/store/slices/cameraDevicesSlice";

interface CameraConfigExposureProps {
    exposureMode: CameraConfig['exposure_mode'];
    exposure: CameraConfig['exposure'];
    onExposureModeChange: (mode: string) => void;
    onExposureValueChange: (value: number) => void;
}

export const CameraConfigExposure: React.FC<CameraConfigExposureProps> = ({
    exposureMode,
    exposure,
    onExposureModeChange,
    onExposureValueChange
}) => (
    <Grid container spacing={2}>
        <Grid size={8}>
            <FormControl size="small" fullWidth>
                <InputLabel>Exposure Mode</InputLabel>
                <Select
                    value={exposureMode}
                    label="Exposure Mode"
                    onChange={(e) => onExposureModeChange(e.target.value)}
                >
                    <MenuItem value="Manual">Manual</MenuItem>
                    <MenuItem value="Auto">Auto</MenuItem>
                    <MenuItem value="Recommended">Recommended</MenuItem>
                </Select>
            </FormControl>
        </Grid>
        <Grid size={4}>
            <TextField
                size="small"
                label="Exposure"
                type="number"
                value={exposure}
                onChange={(e) => onExposureValueChange(Number(e.target.value))}
                inputProps={{
                    min: -12,
                    max: -5,
                    step: 0.5
                }}
                disabled={exposureMode !== 'Manual'}
                fullWidth
            />
        </Grid>
    </Grid>
);
