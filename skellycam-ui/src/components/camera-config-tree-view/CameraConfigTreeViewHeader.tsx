import React from "react";
import {Box, CircularProgress, IconButton, Stack, Tooltip, Typography, useTheme} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import YoutubeSearchedForIcon from "@mui/icons-material/YoutubeSearchedFor";
import SystemUpdateAltIcon from "@mui/icons-material/SystemUpdateAlt";

import {useAppDispatch, useAppSelector} from "@/store";
import {selectSelectedCameras} from "@/store/slices/cameras/cameras-selectors";
import {
    closeCameras,
    connectToCameras,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";

interface CameraConfigTreeViewHeaderProps {
    cameraCount: number;
    isConnected: boolean;
    isLoading: boolean;
    isPaused: boolean;
    onPauseToggle: () => void;
    hasSelectedCameras: boolean;
}

export const CameraConfigTreeViewHeader: React.FC<CameraConfigTreeViewHeaderProps> = ({
    cameraCount,
    isConnected,
    isLoading,
    isPaused,
    onPauseToggle,
    hasSelectedCameras,
}) => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const hasSelected = selectedCameras.length > 0;

    // Track if an action is in progress to prevent duplicate calls
    const [isActionInProgress, setIsActionInProgress] = React.useState(false);

    const handleRefreshCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        if (isActionInProgress || isLoading) return;

        setIsActionInProgress(true);
        try {
            await dispatch(detectCameras({filterVirtual: true})).unwrap();
        } catch (error) {
            console.error('Error detecting cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleConnectOrApply = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        if (isActionInProgress || !hasSelected) return;

        setIsActionInProgress(true);
        try {
            await dispatch(connectToCameras()).unwrap();
            console.log(isConnected ? 'Applied configs to cameras' : 'Connected to cameras');
        } catch (error) {
            console.error('Error with camera operation:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleCloseCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        if (isActionInProgress || !isConnected) return;

        setIsActionInProgress(true);
        try {
            await dispatch(closeCameras()).unwrap();
            console.log('Closed all cameras');
        } catch (error) {
            console.error('Error closing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handlePauseUnpause = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        if (isActionInProgress || !isConnected) return;

        setIsActionInProgress(true);
        try {
            await dispatch(pauseUnpauseCameras()).unwrap();
            onPauseToggle();
        } catch (error) {
            console.error('Error pausing/unpausing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleHeaderClick = (e: React.MouseEvent): void => {
        e.stopPropagation();
    };

    return (
        <Box
            onClick={handleHeaderClick}
            sx={{
                display: "flex",
                alignItems: "center",
                py: 1,
                backgroundColor: theme.palette.primary.main,
                color: theme.palette.primary.contrastText,
            }}
        >
            <VideocamIcon sx={{ml: 2, mr: 1}} />
            <Typography variant="h6" sx={{flexGrow: 1}}>
                Cameras ({cameraCount})
            </Typography>

            <Stack direction="row" spacing={1} sx={{mr: 2}}>
                {/* Connect/Apply Button - Always visible, changes icon and behavior */}
                <Tooltip title={isConnected ? "Apply configuration changes" : "Connect to selected cameras"}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleConnectOrApply}
                            disabled={!hasSelected || isActionInProgress}
                            sx={{color: "inherit"}}
                        >
                            {isConnected ? (
                                <SystemUpdateAltIcon />
                            ) : (
                                <VideocamIcon
                                    sx={{
                                        color: theme.palette.secondary.main,
                                        border: `2px solid ${theme.palette.secondary.main}`,
                                        borderRadius: '4px',
                                        padding: '2px',
                                        scale: '1.6'
                                    }}
                                />
                            )}
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Pause/Play Button - Always visible, disabled when not connected */}
                <Tooltip title={!isConnected ? "Not connected" : isPaused ? "Resume streaming" : "Pause streaming"}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handlePauseUnpause}
                            disabled={!isConnected || isActionInProgress}
                            sx={{
                                color: "inherit",
                                opacity: !isConnected ? 0.4 : 1
                            }}
                        >
                            {isPaused ? <PlayArrowIcon /> : <PauseIcon />}
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Close Button - Always visible, disabled when not connected */}
                <Tooltip title={!isConnected ? "Not connected" : "Disconnect all cameras"}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleCloseCameras}
                            disabled={!isConnected || isActionInProgress}
                            sx={{
                                color: "inherit",
                                opacity: !isConnected ? 0.4 : 1
                            }}
                        >
                            <VideocamOffIcon />
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Refresh/Detect Button - Always visible */}
                <Tooltip title="Detect available cameras">
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleRefreshCameras}
                            disabled={isActionInProgress}
                            sx={{color: "inherit"}}
                        >
                            {isLoading || isActionInProgress ? (
                                <CircularProgress size={20} sx={{color: "inherit"}} />
                            ) : (
                                <YoutubeSearchedForIcon />
                            )}
                        </IconButton>
                    </span>
                </Tooltip>
            </Stack>
        </Box>
    );
};
