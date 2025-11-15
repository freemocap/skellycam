import React from "react";
import {
    Box,
    Collapse,
    IconButton,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import Grid from "@mui/material/Grid2";
import MediationIcon from "@mui/icons-material/Mediation";
import { CameraConfigResolution } from "./CameraConfigResolution";
import { CameraConfigExposure } from "./CameraConfigExposure";
import { CameraConfigRotation } from "./CameraConfigRotation";
import { CameraConfigFramerate } from "./CameraConfigFramerate";
import { CameraConfig, ExposureMode } from "@/store/slices/cameras/cameras-types";
import { useAppDispatch, useAppSelector } from "@/store";
import { selectCameras, configCopiedToAll } from "@/store/slices/cameras";

interface CameraConfigPanelProps {
    config: CameraConfig;
    onConfigChange: (newConfig: CameraConfig) => void;
    isExpanded: boolean;
}

export const CameraConfigPanel: React.FC<CameraConfigPanelProps> = ({
    config,
    onConfigChange,
    isExpanded,
}) => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    // Get total camera count for UI feedback
    const allCameras = useAppSelector(selectCameras);
    const otherCamerasCount = allCameras.length - 1;

    const handleChange = <K extends keyof CameraConfig>(
        key: K,
        value: CameraConfig[K]
    ): void => {
        onConfigChange({
            ...config,
            [key]: value,
        });
    };

    const handleCopyToAllCameras = (): void => {
        dispatch(configCopiedToAll(config.camera_id));
    };

    const handleResolutionChange = (width: number, height: number): void => {
        handleChange("resolution", { width, height });
    };

    const handleRotationChange = (value: string): void => {
        handleChange("rotation", value as unknown as CameraConfig['rotation']);
    };

    const handleFramerateChange = (value: number): void => {
        handleChange("framerate", value);
    };

    const handleExposureModeChange = (mode: ExposureMode): void => {
        handleChange("exposure_mode", mode);
    };

    const handleExposureValueChange = (value: number): void => {
        handleChange("exposure", value);
    };

    return (
        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
            <Box
                sx={{
                    p: 2.5,
                    ml: 7,
                    mr: 2,
                    mb: 1,
                    borderRadius: 1,
                    border: `1px solid ${theme.palette.divider}`,
                    backgroundColor: theme.palette.background.paper,
                }}
            >
                <Grid container spacing={2.5}>
                    {/* Top row with Resolution, Framerate, Rotation, and Copy button */}
                    <Grid size={{ xs: 12, sm: 6, md: 3.5, lg: 3.5 }}>
                        <CameraConfigResolution
                            resolution={config.resolution}
                            onChange={handleResolutionChange}
                        />
                    </Grid>

                    {/*<Grid size={{ xs: 12, sm: 6, md: 2.5, lg: 2.5 }}>*/}
                    {/*    <CameraConfigFramerate*/}
                    {/*        framerate={config.framerate}*/}
                    {/*        onChange={handleFramerateChange}*/}
                    {/*    />*/}
                    {/*</Grid>*/}

                    <Grid size={{ xs: 12, sm: 6, md: 3, lg: 3 }}>
                        <CameraConfigRotation
                            rotation={config.rotation}
                            onChange={handleRotationChange}
                        />
                    </Grid>

                    <Grid size={{ xs: 12, sm: 6, md: 3, lg: 3 }}>
                        <Box
                            sx={{
                                display: 'flex',
                                flexDirection: 'column',
                                justifyContent: 'flex-start',
                                alignItems: 'center',
                            }}
                        >
                            <Tooltip
                                title={
                                    otherCamerasCount > 0
                                        ? `Copy settings to ${otherCamerasCount} other camera${
                                            otherCamerasCount > 1 ? "s" : ""
                                        }`
                                        : "No other cameras to copy to"
                                }
                            >
                                <span>
                                    <IconButton
                                        size="medium"
                                        onClick={handleCopyToAllCameras}
                                        disabled={otherCamerasCount === 0}
                                        aria-label="Copy settings to all cameras"
                                        sx={{
                                            color: theme.palette.primary.contrastText,
                                            border: `1px solid ${theme.palette.divider}`,
                                            '&:hover': {
                                                backgroundColor: theme.palette.primary.main,
                                                color: theme.palette.primary.contrastText,
                                                borderColor: theme.palette.primary.main,
                                            },
                                            '&:disabled': {
                                                color: theme.palette.action.disabled,
                                            },
                                        }}
                                    >
                                        <MediationIcon />
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ mt: 0.5, textAlign: 'center' }}
                            >
                                Copy to All
                            </Typography>
                        </Box>
                    </Grid>

                    {/* Bottom row with Exposure controls (full width with separator) */}
                    <Grid size={12}>
                        <Box sx={{ pt: 1.5, borderTop: `1px solid ${theme.palette.divider}` }}>
                            <CameraConfigExposure
                                exposureMode={config.exposure_mode}
                                exposure={config.exposure}
                                onExposureModeChange={handleExposureModeChange}
                                onExposureValueChange={handleExposureValueChange}
                            />
                        </Box>
                    </Grid>
                </Grid>
            </Box>
        </Collapse>
    );
};