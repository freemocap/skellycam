// CameraConfigExposure.tsx
import * as React from 'react';
import {Box, Slider, ToggleButton, ToggleButtonGroup, Tooltip, Typography} from '@mui/material';
import {CAMERA_DEFAULTS, ExposureMode} from "@/store/slices/cameras-slices/camera-types";

interface CameraConfigExposureProps {
    exposureMode: ExposureMode;
    exposure: number;
    onExposureModeChange: (mode: ExposureMode) => void;
    onExposureValueChange: (value: number) => void;
}

const ValueLabelComponent = (props: {
    children: React.ReactElement;
    value: number;
}) => {
    const {children, value} = props;

    return (
        <Tooltip title={
            <span>
                {`${(1000 / Math.pow(2, -1 * value)).toFixed(3)}ms (1/2`}
                <sup>{value}</sup>
                {` sec)`}
            </span>
        }>
            {children}
        </Tooltip>
    );
};
export const CameraConfigExposure: React.FC<CameraConfigExposureProps> = ({
                                                                              exposureMode = CAMERA_DEFAULTS.exposure_modes[0], // MANUAL
                                                                              exposure = CAMERA_DEFAULTS.exposure.default,
                                                                              onExposureModeChange,
                                                                              onExposureValueChange
                                                                          }) => {
    const [currentExposure, setCurrentExposure] = React.useState<number>(exposure);
    const handleModeChange = (
        event: React.MouseEvent<HTMLElement>,
        newMode: string,
    ) => {
        if (newMode !== null) {
            onExposureModeChange(newMode as ExposureMode);
        }
    };

    const formatExposureValue = (value: number, type: 'label' | 'tooltip') => {
        setCurrentExposure(value)
        if (type === 'tooltip') {
            return `${(1000 / Math.pow(2, -1 * value)).toFixed(3)}ms (1/2`
                + String.fromCharCode(8203)  // zero-width space to ensure proper rendering
                + `<sup>${value}</sup> sec)`;
        }
        return value;
    };
    const baseMarks = [
        {value: CAMERA_DEFAULTS.exposure.min, label: String(CAMERA_DEFAULTS.exposure.min)},
        {value: CAMERA_DEFAULTS.exposure.default, label: `${CAMERA_DEFAULTS.exposure.default} (default)`},
        {value: CAMERA_DEFAULTS.exposure.max, label: String(CAMERA_DEFAULTS.exposure.max)}
    ];
    // Add current exposure value to marks if it doesn't match any existing marks
    const marks = [
        ...baseMarks,
        ...(![CAMERA_DEFAULTS.exposure.min as number,
                CAMERA_DEFAULTS.exposure.default as number,
                CAMERA_DEFAULTS.exposure.max as number].includes(exposure)
                ? [{
                    value: exposure,
                    label: `(${exposure}`,
                }]
                : []
        )
    ].sort((a, b) => a.value - b.value); // Sort marks by value
    return (
        <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
                Camera Exposure
            </Typography>
            <Tooltip title="Choose between automatic or manual exposure control">
                <ToggleButtonGroup
                    color="primary"
                    value={exposureMode}
                    exclusive
                    onChange={handleModeChange}
                    size="small"
                >
                    <ToggleButton value="MANUAL">Manual</ToggleButton>
                    <ToggleButton value="AUTO">Auto</ToggleButton>
                    <ToggleButton value="RECOMMEND">Recommend</ToggleButton>
                </ToggleButtonGroup>
            </Tooltip>
            <Tooltip title="Adjust exposure time, e.g. cv2.VideoCapture.set(cv2.CAP_PROP_EXPOSURE, value)">
                <Box sx={{flexGrow: 1}}>
                    <Slider
                        value={exposure}
                        disabled={exposureMode === 'AUTO' || exposureMode === 'RECOMMEND'}
                        min={-12}
                        max={-5}
                        step={1}
                        marks={marks}
                        valueLabelDisplay="auto"
                        onChange={(_, value) => onExposureValueChange(value as number)}
                        components={{
                            ValueLabel: ValueLabelComponent
                        }}
                    />

                </Box>
            </Tooltip>


        </Box>
    );
};
