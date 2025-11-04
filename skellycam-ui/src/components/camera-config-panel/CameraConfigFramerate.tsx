import React, { useState } from 'react';
import { Box, TextField, Tooltip, useTheme } from '@mui/material';

interface CameraConfigFramerateProps {
    framerate: number;
    onChange: (value: number) => void;
}

const FRAMERATE_CONSTRAINTS = {
    min: 1,
    max: 1000,
    default: 30
};

export const CameraConfigFramerate: React.FC<CameraConfigFramerateProps> = ({
    framerate = FRAMERATE_CONSTRAINTS.default,
    onChange
}) => {
    const theme = useTheme();
    const [localValue, setLocalValue] = useState<string>(framerate.toFixed(2));
    const [error, setError] = useState<string>('');

    const validateAndUpdate = (value: string): void => {
        const numValue = parseFloat(value);

        if (value === '' || isNaN(numValue)) {
            setError('Enter a valid number');
            return;
        }

        if (numValue < FRAMERATE_CONSTRAINTS.min) {
            setError(`Min: ${FRAMERATE_CONSTRAINTS.min} FPS`);
            return;
        }

        if (numValue > FRAMERATE_CONSTRAINTS.max) {
            setError(`Max: ${FRAMERATE_CONSTRAINTS.max} FPS`);
            return;
        }

        setError('');
        const roundedValue = Math.round(numValue * 100) / 100;
        onChange(roundedValue);
    };

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
        const value = event.target.value;
        setLocalValue(value);
    };

    const handleBlur = (): void => {
        validateAndUpdate(localValue);

        // Reset to valid value if invalid, otherwise format to 2 decimals
        if (error) {
            setLocalValue(framerate.toFixed(2));
            setError('');
        } else {
            setLocalValue(parseFloat(localValue).toFixed(2));
        }
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>): void => {
        if (event.key === 'Enter') {
            validateAndUpdate(localValue);
            if (error) {
                setLocalValue(framerate.toFixed(2));
                setError('');
            } else {
                setLocalValue(parseFloat(localValue).toFixed(2));
            }
            event.currentTarget.blur();
        }
    };

    return (
        <Box>
            <Tooltip title="Set target frames per second (FPS) for camera capture">
                <TextField
                    label="Framerate"
                    value={localValue}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    onKeyDown={handleKeyDown}
                    type="number"
                    size="small"
                    error={!!error}
                    fullWidth
                    inputProps={{
                        min: FRAMERATE_CONSTRAINTS.min,
                        max: FRAMERATE_CONSTRAINTS.max,
                        step: 0.01,
                    }}
                    sx={{
                        '& .MuiInputLabel-root': {
                            color: theme.palette.text.primary,
                        },
                        '& .MuiOutlinedInput-root': {
                            color: theme.palette.text.primary,
                            '& fieldset': {
                                borderColor: theme.palette.divider,
                            },
                            '&:hover fieldset': {
                                borderColor: theme.palette.primary.main,
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: theme.palette.primary.main,
                            },
                        },
                        '& .MuiFormHelperText-root': {
                            color: error ? theme.palette.error.main : theme.palette.text.secondary,
                        },
                    }}
                />
            </Tooltip>
        </Box>
    );
};