import React from "react";
import {Box, CircularProgress, IconButton, Stack, Tooltip, Typography, useTheme,} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import YoutubeSearchedForIcon from "@mui/icons-material/YoutubeSearchedFor";
import SystemUpdateAltIcon from "@mui/icons-material/SystemUpdateAlt";

import {useAppDispatch, useAppSelector} from "@/store";
import {selectSelectedCameras,} from "@/store/slices/cameras/cameras-selectors";
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

    const handleRefreshCameras = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(detectCameras({ filterVirtual: true }));
    };

    const handleConnectCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        if (hasSelected) {
            try {
                await dispatch(connectToCameras()).unwrap();
                console.log('Connected to selected cameras');
            } catch (error) {
                console.error('Error connecting to cameras:', error);
            }
        }
    };

    const handleCloseCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();
        try {
            await dispatch(closeCameras()).unwrap();
            console.log('Closed all cameras');
        } catch (error) {
            console.error('Error closing cameras:', error);
        }
    };

    const handlePauseUnpause = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(pauseUnpauseCameras());
        onPauseToggle();
    };

    // Stop propagation on the entire header box to prevent any clicks from bubbling
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
                                disabled={!hasSelected || isLoading}
                                sx={{ color: "inherit" }}
                            >
                                <VideocamIcon sx={{
                                    color: theme.palette.secondary.main,
                                    border: `2px solid ${theme.palette.secondary.main}`,
                                    borderRadius: '4px',
                                    padding: '2px',
                                    scale: '1.6'

                                }}/>
                            </IconButton>
                        </span>
                    </Tooltip>
                ) : (
                    <>
                        {/* Update Configs Button - only show when connected */}
                        <Tooltip title="Apply configuration changes">
                            <IconButton
                                size="small"
                                onClick={handleConnectCameras}
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
