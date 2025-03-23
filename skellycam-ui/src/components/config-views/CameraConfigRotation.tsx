import { FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import * as React from "react";
import { CameraConfig } from "@/store/slices/cameraDevicesSlice";

interface CameraConfigRotationProps {
    rotation: CameraConfig['rotation'];
    onChange: (value: string) => void;
}

export const CameraConfigRotation: React.FC<CameraConfigRotationProps> = ({
    rotation,
    onChange
}) => (
    <FormControl size="small" fullWidth>
        <InputLabel>Rotation</InputLabel>
        <Select
            value={rotation}
            label="Rotation"
            onChange={(e) => onChange(e.target.value)}
        >
            <MenuItem value="0">0°</MenuItem>
            <MenuItem value="90">90°</MenuItem>
            <MenuItem value="180">180°</MenuItem>
            <MenuItem value="270">270°</MenuItem>
        </Select>
    </FormControl>
);
