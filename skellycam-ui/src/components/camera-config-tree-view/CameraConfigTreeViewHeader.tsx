import React from "react";
import {
    Box,
    CircularProgress,
    IconButton,
    Stack,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import RefreshIcon from "@mui/icons-material/Refresh";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import YoutubeSearchedForIcon from "@mui/icons-material/YoutubeSearchedFor";
import SystemUpdateAltIcon from "@mui/icons-material/SystemUpdateAlt";

import { useAppDispatch, useAppSelector } from "@/store";
import {
    selectSelectedCameras,
    selectCameraLoadingState,
} from "@/store/slices/cameras/cameras-selectors";
import {
    connectToCameras,
    closeCameras,
    pauseUnpauseCameras,
    detectCameras,
    updateCameraConfigs,
} from "@/store/slices/cameras/cameras-thunks";

interface CameraConfigTreeViewHeaderProps {
    cameraCount: number;
    isConnected: boolean;
    isLoading: boolean;
    isPaused: boolean;
    onPauseToggle: () => void;
}

export const CameraConfigTreeViewHeader: React.FC<CameraConfigTreeViewHeaderProps> = ({
                                                                                          cameraCount,
                                                                                          isConnected,
                                                                                          isLoading,
                                                                                          isPaused,
                                                                                          onPauseToggle,
                                                                                      }) => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const hasSelectedCameras = selectedCameras.length > 0;

    const handleRefreshCameras = (): void => {
        dispatch(detectCameras({ filterVirtual: true }));
    };

    const handleConnectCameras = async (): Promise<void> => {
        if (hasSelectedCameras) {
            try {
                await dispatch(connectToCameras()).unwrap();
                console.log('Connected to selected cameras');
            } catch (error) {
                console.error('Error connecting to cameras:', error);
            }
        }
    };

    const handleCloseCameras = async (): Promise<void> => {
        try {
            await dispatch(closeCameras()).unwrap();
            console.log('Closed all cameras');
        } catch (error) {
            console.error('Error closing cameras:', error);
        }
    };

    const handlePauseUnpause = (): void => {
        dispatch(pauseUnpauseCameras());
        onPauseToggle();
    };

    const handleUpdateConfigs = async (): Promise<void> => {
        if (isConnected) {
            try {
                await dispatch(updateCameraConfigs()).unwrap();
                console.log('Updated camera configurations');
            } catch (error) {
                console.error('Error updating configs:', error);
            }
        }
    };

    return (
        <Box
            sx={{
                display: "flex",
                alignItems: "center",
                py: 1,
                backgroundColor: theme.palette.primary.main,
                color: theme.palette.primary.contrastText,
            }}
        >
            <VideocamIcon sx={{ ml: 2, mr: 1 }} />
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
                Cameras ({cameraCount})
            </Typography>

            <Stack direction="row" spacing={1} sx={{ mr: 2 }}>
                {/* Connect/Disconnect Button */}
                {!isConnected ? (
                    <Tooltip title="Connect to selected cameras">
                        <span>
                            <IconButton
                                size="small"
                                onClick={handleConnectCameras}
                                disabled={!hasSelectedCameras || isLoading}
                                sx={{ color: "inherit" }}
                            >
                                <VideocamIcon />
                            </IconButton>
                        </span>
                    </Tooltip>
                ) : (
                    <>
                        {/* Update Configs Button - only show when connected */}
                        <Tooltip title="Apply configuration changes">
                            <IconButton
                                size="small"
                                onClick={handleUpdateConfigs}
                                disabled={isLoading}
                                sx={{ color: "inherit" }}
                            >
                                <SystemUpdateAltIcon />
                            </IconButton>
                        </Tooltip>

                        {/* Disconnect Button */}
                        <Tooltip title="Disconnect all cameras">
                            <IconButton
                                size="small"
                                onClick={handleCloseCameras}
                                sx={{ color: "inherit" }}
                            >
                                <VideocamOffIcon />
                            </IconButton>
                        </Tooltip>
                    </>
                )}

                {/* Pause/Unpause Button - only show when connected */}
                {isConnected && (
                    <Tooltip title={isPaused ? "Resume streaming" : "Pause streaming"}>
                        <IconButton
                            size="small"
                            onClick={handlePauseUnpause}
                            sx={{ color: "inherit" }}
                        >
                            {isPaused ? <PlayArrowIcon /> : <PauseIcon />}
                        </IconButton>
                    </Tooltip>
                )}

                {/* Refresh/Detect Button */}
                <Tooltip title="Detect available cameras">
                    <IconButton
                        size="small"
                        onClick={handleRefreshCameras}
                        disabled={isLoading}
                        sx={{ color: "inherit" }}
                    >
                        {isLoading ? (
                            <CircularProgress size={20} sx={{ color: "inherit" }} />
                        ) : (
                            <YoutubeSearchedForIcon />
                        )}
                    </IconButton>
                </Tooltip>
            </Stack>
        </Box>
    );
};
