import {Accordion, AccordionDetails, Box, List, Paper, Stack, Typography, useTheme} from "@mui/material";
import * as React from "react";
import {useEffect, useState} from "react";
import AccordionSummary from "@mui/material/AccordionSummary";
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import VideocamIcon from '@mui/icons-material/Videocam';
import {CameraConfigPanel} from "@/components/available-cameras-panel/CameraConfigPanel";
import {CameraListItem} from "@/components/available-cameras-panel/CameraListItem";
import {RefreshDetectedCamerasButton} from "@/components/available-cameras-panel/RefreshDetectedCameras";
import {createDefaultCameraConfig, SerializedMediaDeviceInfo} from "@/store/slices/cameras-slices/camera-types";
import {toggleCameraSelection} from "@/store/slices/cameras-slices/detectedCamerasSlice";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {setUserSelectedCameraConfigs} from "@/store/slices/cameras-slices/userCameraConfigs";
import {ConnectToCamerasButton} from "@/components/available-cameras-panel/ConnectToCamerasButton";
import {detectBrowserDevices} from "@/store/thunks/detect-cameras-thunks";

export const AvailableCamerasView = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const browserDetectedDevices = useAppSelector(state => state.detectedCameras.browserDetectedCameras);
    const userConfigs = useAppSelector(state => state.userCameraConfigs.userConfigs);
    const isLoading = useAppSelector(state => state.detectedCameras.isLoading);
    const [expandedConfigs, setExpandedConfigs] = useState<Set<string>>(new Set());

    // Handle expanding/collapsing camera config panels
    const toggleConfig = (deviceId: string) => {
        setExpandedConfigs(prev => {
            const newSet = new Set(prev);
            if (newSet.has(deviceId)) {
                newSet.delete(deviceId);
            } else {
                newSet.add(deviceId);
            }
            return newSet;
        });
    };


    // Initial camera detection
    useEffect(() => {
        dispatch(detectBrowserDevices(true));
    }, [dispatch]);

    // Generate default config for a camera
    const getDefaultConfig = (device: SerializedMediaDeviceInfo) =>
        createDefaultCameraConfig(device.index, device.label);

    return (
        <Accordion
            defaultExpanded
            sx={{
                borderRadius: 2,
                '&:before': { display: 'none' },
                boxShadow: theme.shadows[3]
            }}
        >
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                backgroundColor: theme.palette.primary.main,
                borderTopLeftRadius: 8,
                borderTopRightRadius: 8,
            }}>

                <AccordionSummary
                    expandIcon={<ExpandMoreIcon sx={{ color: theme.palette.primary.contrastText }} />}
                    sx={{
                        flex: 1,
                        color: theme.palette.primary.contrastText,
                        '&:hover': {
                            backgroundColor: theme.palette.primary.light,
                        }
                    }}
                >
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <VideocamIcon />
                        <Typography variant="subtitle1" fontWeight="medium">
                            Available Cameras
                        </Typography>
                    </Stack>
                </AccordionSummary>
                <ConnectToCamerasButton/>

                <Box sx={{ pr: 2 }}>
                    <RefreshDetectedCamerasButton isLoading={isLoading} />
                </Box>
            </Box>

            <AccordionDetails sx={{ p: 2, bgcolor: 'background.default' }}>
                <Paper
                    elevation={0}
                    sx={{
                        bgcolor: 'background.paper',
                        borderRadius: 2,
                        overflow: 'hidden'
                    }}
                >
                    <List dense disablePadding>
                        {browserDetectedDevices.map((device, index) => (
                            <React.Fragment key={device.deviceId}>
                                <CameraListItem
                                    device={device}
                                    isLast={index === browserDetectedDevices.length - 1}
                                    isConfigExpanded={expandedConfigs.has(device.deviceId)}
                                    onToggleSelect={() => dispatch(toggleCameraSelection(device.deviceId))}
                                    onToggleConfig={() => toggleConfig(device.deviceId)}
                                />
                                {device.selected && (
                                    <CameraConfigPanel
                                        config={userConfigs?.[device.deviceId] || getDefaultConfig(device)}
                                        onConfigChange={(newConfig) => {
                                            dispatch(setUserSelectedCameraConfigs({
                                                deviceId: device.deviceId,
                                                config: newConfig
                                            }));
                                        }}
                                        isExpanded={expandedConfigs.has(device.deviceId)}
                                    />
                                )}
                            </React.Fragment>
                        ))}
                    </List>

                    {browserDetectedDevices.length === 0 && (
                        <Box
                            sx={{
                                p: 3,
                                textAlign: 'center',
                                bgcolor: 'background.paper',
                                borderRadius: 1
                            }}
                        >
                            <Typography
                                variant="body1"
                                color="text.secondary"
                            >
                                No cameras detected
                            </Typography>
                            <Typography
                                variant="caption"
                                color="text.disabled"
                                sx={{ mt: 1, display: 'block' }}
                            >
                                Click refresh to scan for available cameras
                            </Typography>
                        </Box>
                    )}
                </Paper>
            </AccordionDetails>
        </Accordion>
    );
};
