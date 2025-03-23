import {
    Accordion,
    AccordionDetails,
    Box,
    List,
    Paper,
    Stack,
    Typography,
    useTheme
} from "@mui/material";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { setUserSelectedCameraConfigs, toggleCameraSelection } from "@/store/slices/cameraDevicesSlice";
import * as React from "react";
import { useEffect, useState } from "react";
import { detectBrowserDevices } from "@/store/thunks/camera-thunks";
import IconButton from "@mui/material/IconButton";
import RefreshIcon from '@mui/icons-material/Refresh';
import AccordionSummary from "@mui/material/AccordionSummary";
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import VideocamIcon from '@mui/icons-material/Videocam';
import {CameraConfigPanel} from "@/components/config-views/CameraConfigPanel";
import {CameraListItem} from "@/components/config-views/CameraListItem";

export const AvailableCamerasView = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const browserDetectedDevices = useAppSelector(state => state.cameraDevices.browser_detected_devices);
    const userConfigs = useAppSelector(state => state.cameraDevices.user_selected_camera_configs);
    const isLoading = useAppSelector(state => state.cameraDevices.isLoading);
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

    // Handle refresh button click
    const handleRefresh = (event: React.MouseEvent) => {
        event.stopPropagation();
        dispatch(detectBrowserDevices(true));
    };

    // Initial camera detection
    useEffect(() => {
        dispatch(detectBrowserDevices(true));
    }, [dispatch]);

    // Generate default config for a camera
    const getDefaultConfig = (device: typeof browserDetectedDevices[0]) => ({
        camera_id: device.index,
        camera_name: device.label || `Camera ${device.index}`,
        use_this_camera: true,
        resolution: { width: 1280, height: 720 },
        color_channels: 3,
        pixel_format: "BGR",
        exposure_mode: "Manual",
        exposure:  -7,
        framerate: 30,
        rotation: "0",
        capture_fourcc: "MJPG",
        writer_fourcc: "MJPG"
    });

    return (
        <Accordion
            defaultExpanded
            sx={{
                borderRadius: 2,
                '&:before': { display: 'none' },
                boxShadow: theme.shadows[3]
            }}
        >
            <AccordionSummary
                expandIcon={<ExpandMoreIcon sx={{ color: theme.palette.primary.contrastText }} />}
                sx={{
                    backgroundColor: theme.palette.primary.main,
                    color: theme.palette.primary.contrastText,
                    borderTopLeftRadius: 8,
                    borderTopRightRadius: 8,
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
                    <IconButton
                        onClick={handleRefresh}
                        size="small"
                        sx={{
                            color: theme.palette.primary.contrastText,
                            ml: 1,
                            '&:hover': {
                                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                            }
                        }}
                        disabled={isLoading}
                        title="Refresh available cameras"
                    >
                        <RefreshIcon fontSize="small" />
                    </IconButton>
                </Stack>
            </AccordionSummary>

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
                                                ...userConfigs,
                                                [device.deviceId]: newConfig
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
