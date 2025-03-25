// CameraConfigRotation.tsx
import * as React from 'react';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import {Box, Tooltip} from '@mui/material';
import {RotationOptionSchema} from "@/store/slices/cameras-slices/camera-types";
import {z} from 'zod';

interface CameraConfigRotationProps {
    rotation: z.infer<typeof RotationOptionSchema>;
    onChange: (rotation: z.infer<typeof RotationOptionSchema>) => void;
}

export const CameraConfigRotation: React.FC<CameraConfigRotationProps> = ({
    rotation,
    onChange
}) => {
    const handleChange = (
        event: React.MouseEvent<HTMLElement>,
        newRotation: string,
    ) => {
        if (newRotation !== null) {
            onChange(newRotation as z.infer<typeof RotationOptionSchema>);
        }
    };

    return (
        <Box>

            <Tooltip title="Select camera image rotation">
                <ToggleButtonGroup
                    color="primary"
                    value={rotation}
                    size="small"
                    exclusive
                    onChange={handleChange}
                    aria-label="camera rotation"
                >
                    <ToggleButton value="0">0°</ToggleButton>
                    <ToggleButton value="90">90°</ToggleButton>
                    <ToggleButton value="180">180°</ToggleButton>
                    <ToggleButton value="270">270°</ToggleButton>
                </ToggleButtonGroup>
            </Tooltip>
        </Box>
    );
}
