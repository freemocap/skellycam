import {
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Paper,
    Checkbox,
    Typography,
    Box, Stack
} from "@mui/material";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { toggleCameraSelection } from "@/store/slices/cameraDevicesSlice";
import {useEffect} from "react";
import {detectBrowserDevices} from "@/store/thunks/camera-thunks";
import IconButton from "@mui/material/IconButton";
import RefreshIcon from '@mui/icons-material/Refresh';
export const AvailableCamerasView = () => {
    const dispatch = useAppDispatch();
    const browserDetectedDevices = useAppSelector(state => state.cameraDevices.browser_detected_devices);
    const isLoading = useAppSelector(state => state.cameraDevices.isLoading);

    const handleRefresh = () => {
        dispatch(detectBrowserDevices(true));
    };

    useEffect(() => {
        dispatch(detectBrowserDevices(true));
    }, [dispatch]);
    return (
        <Paper elevation={3} sx={{
            p: 2,
            backgroundColor: 'background.paper',
            borderRadius: 2,
            maxWidth: 600,
        }}>
            <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                sx={{ mb: 1 }}
            >
                <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
                    Available Cameras
                </Typography>
                <IconButton
                    onClick={handleRefresh}
                    size="small"
                    color="primary"
                    disabled={isLoading}
                >
                    <RefreshIcon />
                </IconButton>
            </Stack>
            <List dense sx={{ bgcolor: 'background.default', borderRadius: 1 }}>
                {browserDetectedDevices.map(device => (
                    <ListItem
                        key={device.deviceId}
                        sx={{
                            '&:hover': {
                                backgroundColor: 'action.hover',
                            },
                            borderBottom: '1px solid',
                            borderColor: 'divider',
                        }}
                    >
                        <ListItemIcon>
                            <Checkbox
                                edge="start"
                                checked={device.selected || false}
                                onChange={() => dispatch(toggleCameraSelection(device.deviceId))}
                                sx={{ color: 'primary.main' }}
                            />
                        </ListItemIcon>
                        <ListItemText
                            primary={
                                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                    <Typography
                                        component="span"
                                        variant="body2"
                                        color="primary.main"
                                        sx={{ mr: 1, fontWeight: 'bold' }}
                                    >
                                        Camera  {device.index}:
                                    </Typography>
                                    <Typography component="span" variant="body2">
                                        {device.label || `Unknown Device ${device.index}`}
                                    </Typography>
                                </Box>
                            }
                        />
                    </ListItem>
                ))}
            </List>

            {browserDetectedDevices.length === 0 && (
                <Typography
                    variant="body2"
                    sx={{
                        textAlign: 'center',
                        py: 2,
                        color: 'text.secondary'
                    }}
                >
                    No cameras detected
                </Typography>
            )}
        </Paper>
    );
};
