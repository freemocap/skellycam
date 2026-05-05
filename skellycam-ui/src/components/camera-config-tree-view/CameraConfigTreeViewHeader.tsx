import React from "react";
import {Box, CircularProgress, IconButton, Stack, Tooltip, Typography, useTheme} from "@mui/material";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import YoutubeSearchedForIcon from "@mui/icons-material/YoutubeSearchedFor";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";

import {useAppDispatch, useAppSelector} from "@/store";
import {selectSelectedCameras} from "@/store/slices/cameras/cameras-selectors";
import {
    closeCameras,
    camerasConnectOrUpdate,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import {savedSettingsCleared} from "@/store/slices/cameras/cameras-slice";
import {useTranslation} from 'react-i18next';
import {useServer} from "@/services/server/ServerContextProvider";

interface CameraConfigTreeViewHeaderProps {
    cameraCount: number;
    isLoading: boolean;
    isPaused: boolean;
    hasSelectedCameras: boolean;
}

export const CameraConfigTreeViewHeader: React.FC<CameraConfigTreeViewHeaderProps> = ({
                                                                                          cameraCount,
                                                                                          isLoading,
                                                                                          isPaused,
                                                                                      }) => {
    const theme = useTheme();
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const {isConnected, connectedCameraIds} = useServer();
    const hasCamerasConnected = connectedCameraIds.length > 0;
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const hasSelected = selectedCameras.length > 0;

    const [isActionInProgress, setIsActionInProgress] = React.useState(false);

    const handleRefreshCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();

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

        setIsActionInProgress(true);
        try {
            await dispatch(camerasConnectOrUpdate()).unwrap();
        } catch (error) {
            console.error('Error with camera operation:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleCloseCameras = async (e: React.MouseEvent): Promise<void> => {
        e.stopPropagation();

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

        setIsActionInProgress(true);
        try {
            await dispatch(pauseUnpauseCameras()).unwrap();
        } catch (error) {
            console.error('Error pausing/unpausing cameras:', error);
        } finally {
            setIsActionInProgress(false);
        }
    };

    const handleClearSavedSettings = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(savedSettingsCleared());
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
                backgroundColor: theme.palette.primary.dark,
                color: theme.palette.primary.contrastText,
            }}
        >
            <VideocamIcon sx={{ml: 2, mr: 1}}/>
            <Typography variant="h6" sx={{flexGrow: 1}}>
                {t('camerasCount', {count: cameraCount})}
            </Typography>

            <Stack direction="row" spacing={1} sx={{mr: 2}}>
                {/* Connect/Apply Button - Always visible, changes icon and behavior */}
                <Tooltip title={t(!isConnected ? "connectServerFirst" : "connectCameras")}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleConnectOrApply}
                            disabled={!isConnected || isActionInProgress}
                            sx={{color: "inherit", "&.Mui-disabled": {opacity: 0.5}}}
                        >

                        <Box sx={{position: 'relative', display: 'inline-flex', width: 24, height: 24}}>
                            <VideocamIcon
                                sx={{
                                    color: theme.palette.secondary.main,
                                    fontSize: 24,
                                }}
                            />
                            <ArrowDownwardIcon
                                sx={{
                                    position: 'absolute',
                                    top: -4,
                                    left: '50%',
                                    transform: 'translateX(-50%)',
                                    fontSize: 10,
                                    color: theme.palette.secondary.main,
                                    strokeWidth: 2,
                                    stroke: theme.palette.secondary.main,
                                }}
                            />
                        </Box>

                            
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Pause/Play Button - Always visible, disabled when no cameras connected */}
                <Tooltip title={isPaused ? t("resumeStreaming") : t("pauseStreaming")}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handlePauseUnpause}
                            disabled={!hasCamerasConnected || isActionInProgress}
                            sx={{color: "inherit", "&.Mui-disabled": {opacity: 0.5}}}
                        >
                            {isPaused ? <PlayArrowIcon/> : <PauseIcon/>}
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Close Button - Always visible, disabled when no cameras connected */}
                <Tooltip title={t("closeAllCameras")}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleCloseCameras}
                            disabled={!hasCamerasConnected || isActionInProgress}
                            sx={{color: "inherit", "&.Mui-disabled": {opacity: 0.5}}}
                        >
                            <VideocamOffIcon/>
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Refresh/Detect Button - Always visible */}
                <Tooltip title={t(!isConnected ? "connectServerFirst" : "detectCameras")}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleRefreshCameras}
                            disabled={!isConnected || isActionInProgress}
                            sx={{color: "inherit", "&.Mui-disabled": {opacity: 0.5}}}
                        >
                            {isLoading || isActionInProgress ? (
                                <CircularProgress size={20} sx={{color: "inherit"}}/>
                            ) : (
                                <YoutubeSearchedForIcon/>
                            )}
                        </IconButton>
                    </span>
                </Tooltip>

                {/* Clear Saved Settings Button */}
                <Tooltip title={t("clearCameraSettings")}>
                    <span>
                        <IconButton
                            size="small"
                            onClick={handleClearSavedSettings}
                            sx={{color: "inherit"}}
                        >
                            <DeleteSweepIcon/>
                        </IconButton>
                    </span>
                </Tooltip>
            </Stack>
        </Box>
    );
};
