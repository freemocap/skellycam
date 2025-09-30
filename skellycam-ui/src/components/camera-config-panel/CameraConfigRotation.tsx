import React from 'react';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { Box, Tooltip, useTheme } from '@mui/material';
import { ROTATION_OPTIONS, RotationValue } from '@/store/slices/cameras/cameras-types';

interface CameraConfigRotationProps {
    rotation?: RotationValue;
    onChange: (rotation: RotationValue) => void;
}

// Map rotation values to degree labels
const ROTATION_DEGREE_LABELS: Record<RotationValue, string> = {
    [-1]: '0°',
    [0]: '90°',
    [1]: '180°',
    [2]: '270°',
};

export const CameraConfigRotation: React.FC<CameraConfigRotationProps> = ({
                                                                              rotation = -1,
                                                                              onChange
                                                                          }) => {
    const theme = useTheme();

    const handleChange = (
        event: React.MouseEvent<HTMLElement>,
        newRotation: RotationValue | null,
    ): void => {
        if (newRotation !== null) {
            onChange(newRotation);
        }
    };

    return (
        <Box>
            <Tooltip title="Select camera image rotation">
                <ToggleButtonGroup
                    color={theme.palette.primary.main as any}
                    value={rotation}
                    size="small"
                    exclusive
                    onChange={handleChange}
                    aria-label="camera rotation"
                    sx={{
                        '& .MuiToggleButton-root.Mui-selected': {
                            backgroundColor: theme.palette.primary.main,
                            color: theme.palette.primary.contrastText,
                            border: `1px solid ${theme.palette.text.secondary}`,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.light,
                            },
                        }
                    }}
                >
                    {ROTATION_OPTIONS.map((option: RotationValue) => (
                        <ToggleButton key={option} value={option}>
                            {ROTATION_DEGREE_LABELS[option]}
                        </ToggleButton>
                    ))}
                </ToggleButtonGroup>
            </Tooltip>
        </Box>
    );
};
