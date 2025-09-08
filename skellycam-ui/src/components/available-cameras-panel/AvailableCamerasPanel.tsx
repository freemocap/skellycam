// skellycam-ui/src/components/available-cameras-panel/AvailableCamerasPanel.tsx
import React, { useEffect, useState, useMemo } from "react";
import {
    Box,
    Paper,
    Stack,
    Typography,
    useTheme,
    Chip,
    IconButton,
    Tooltip,
} from "@mui/material";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import RefreshIcon from "@mui/icons-material/Refresh";
import SettingsIcon from "@mui/icons-material/Settings";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import CircularProgress from "@mui/material/CircularProgress";

import { CameraConfigPanel } from "./CameraConfigPanel";
import {selectIsServerAlive, selectIsWebSocketConnected, useAppDispatch, useAppSelector} from "@/store";
import {
    selectAllCameras,
    selectCameraLoadingState,
    selectCameraConnectionStatus,
} from "@/store/slices/cameras/cameras-selectors";
import {
    cameraSelectionToggled,
    cameraConfigUpdated,
} from "@/store/slices/cameras/cameras-slice";
import {
    detectCameras,
    connectToCameras,
    closeCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import { CameraConfig, CameraDevice } from "@/store/slices/cameras/cameras-types";

interface CameraTreeItemProps {
    camera: CameraDevice;
    isConfigExpanded: boolean;
    onToggleConfig: () => void;
    onConfigChange: (cameraId: string, newConfig: CameraConfig) => void;
}

const CameraTreeItem: React.FC<CameraTreeItemProps> = ({
                                                           camera,
                                                           isConfigExpanded,
                                                           onToggleConfig,
                                                           onConfigChange,
                                                       }) => {
    const dispatch = useAppDispatch();
    const theme = useTheme();

    const handleToggleSelection = (e: React.MouseEvent) => {
        e.stopPropagation();
        dispatch(cameraSelectionToggled(camera.cameraId));
    };

    const handleToggleConfig = (e: React.MouseEvent) => {
        e.stopPropagation();
        onToggleConfig();
    };

    const getStatusColor = (): string => {
        switch (camera.status) {
            case "CONNECTED":
                return theme.palette.success.main;
            case "AVAILABLE":
                return theme.palette.info.main;
            case "ERROR":
                return theme.palette.error.main;
            case "IN_USE":
                return theme.palette.warning.main;
            default:
                return theme.palette.grey[500];
        }
    };

    return (
        <TreeItem
            itemId={`camera-${camera.cameraId}`}
            label={
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        py: 0.5,
                        pr: 1,
                    }}
                >
                    <IconButton
                        size="small"
                        onClick={handleToggleSelection}
                        sx={{ mr: 1 }}
                    >
                        {camera.selected ? (
                            <CheckCircleIcon color="primary" />
                        ) : (
                            <RadioButtonUncheckedIcon />
                        )}
                    </IconButton>

                    <VideocamIcon
                        sx={{
                            mr: 1,
                            color: getStatusColor(),
                        }}
                    />

                    <Typography variant="body2" sx={{ flexGrow: 1 }}>
                        {camera.label || `Camera ${camera.index}`}
                    </Typography>

                    <Chip
                        label={camera.status}
                        size="small"
                        sx={{
                            mr: 1,
                            backgroundColor: getStatusColor(),
                            color: theme.palette.getContrastText(getStatusColor()),
                        }}
                    />

                    {camera.selected && (
                        <Tooltip title="Configure camera">
                            <IconButton
                                size="small"
                                onClick={handleToggleConfig}
                                color={isConfigExpanded ? "primary" : "default"}
                            >
                                <SettingsIcon />
                            </IconButton>
                        </Tooltip>
                    )}
                </Box>
            }
        >
            {camera.selected && (
                <Box sx={{ pl: 2 }}>
                    <CameraConfigPanel
                        config={camera.config}
                        onConfigChange={(newConfig) =>
                            onConfigChange(camera.cameraId, newConfig)
                        }
                        isExpanded={isConfigExpanded}
                    />
                </Box>
            )}
        </TreeItem>
    );
};

export const AvailableCamerasPanel: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    // Redux state - using RTK selectors for server/websocket status
    const cameras = useAppSelector(selectAllCameras);
    const isLoading = useAppSelector(selectCameraLoadingState);
    const connectionStatus = useAppSelector(selectCameraConnectionStatus);
    const isWebSocketConnected = useAppSelector(selectIsWebSocketConnected);
    const isServerAlive = useAppSelector(selectIsServerAlive);

    // Local state
    const [expandedConfigs, setExpandedConfigs] = useState<Set<string>>(new Set());
    const [isPaused, setIsPaused] = useState<boolean>(false);
    const [expandedItems, setExpandedItems] = useState<string[]>(["cameras-root"]);

    // Memoized values for performance
    const selectedCameras = useMemo(
        () => cameras.filter((cam) => cam.selected),
        [cameras]
    );

    const hasSelectedCameras = selectedCameras.length > 0;
    const isConnectedToCameras = connectionStatus === "connected";

    // Initial camera detection - only when server and websocket are connected
    useEffect(() => {
        if (isWebSocketConnected && isServerAlive && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [isWebSocketConnected, isServerAlive, cameras.length, dispatch]);

    // Handler functions
    const handleRefreshCameras = () => {
        dispatch(detectCameras({ filterVirtual: true }));
    };

    const handleConnectCameras = () => {
        if (hasSelectedCameras) {
            dispatch(connectToCameras());
        }
    };

    const handleCloseCameras = () => {
        dispatch(closeCameras());
    };

    const handlePauseUnpause = () => {
        dispatch(pauseUnpauseCameras());
        setIsPaused(!isPaused);
    };

    const toggleConfig = (cameraId: string) => {
        setExpandedConfigs((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(cameraId)) {
                newSet.delete(cameraId);
            } else {
                newSet.add(cameraId);
            }
            return newSet;
        });
    };

    const handleConfigChange = (cameraId: string, newConfig: CameraConfig) => {
        dispatch(
            cameraConfigUpdated({
                cameraId,
                config: newConfig,
            })
        );
    };

    const handleExpandedItemsChange = (event: React.SyntheticEvent, itemIds: string[]) => {
        setExpandedItems(itemIds);
    };

    return (
        <Paper
            elevation={3}
            sx={{
                borderRadius: 2,
                overflow: "hidden",
                mb: 2,
            }}
        >
            <SimpleTreeView
                expandedItems={expandedItems}
                onExpandedItemsChange={handleExpandedItemsChange}
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon,
                }}
            >
                <TreeItem
                    itemId="cameras-root"
                    label={
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
                                Cameras ({cameras.length})
                            </Typography>

                            <Stack direction="row" spacing={1} sx={{ mr: 2 }}>
                                {/* Connect/Disconnect Button */}
                                {!isConnectedToCameras ? (
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
                                    <Tooltip title="Disconnect cameras">
                                        <IconButton
                                            size="small"
                                            onClick={handleCloseCameras}
                                            sx={{ color: "inherit" }}
                                        >
                                            <VideocamOffIcon />
                                        </IconButton>
                                    </Tooltip>
                                )}

                                {/* Pause/Unpause Button */}
                                {isConnectedToCameras && (
                                    <Tooltip title={isPaused ? "Resume" : "Pause"}>
                                        <IconButton
                                            size="small"
                                            onClick={handlePauseUnpause}
                                            sx={{ color: "inherit" }}
                                        >
                                            {isPaused ? "▶" : "⏸"}
                                        </IconButton>
                                    </Tooltip>
                                )}

                                {/* Refresh Button */}
                                <Tooltip title="Refresh camera list">
                                    <IconButton
                                        size="small"
                                        onClick={handleRefreshCameras}
                                        disabled={isLoading}
                                        sx={{ color: "inherit" }}
                                    >
                                        {isLoading ? (
                                            <CircularProgress
                                                size={20}
                                                sx={{ color: "inherit" }}
                                            />
                                        ) : (
                                            <RefreshIcon />
                                        )}
                                    </IconButton>
                                </Tooltip>
                            </Stack>
                        </Box>
                    }
                >
                    {cameras.length === 0 ? (
                        <TreeItem
                            itemId="no-cameras"
                            label={
                                <Box
                                    sx={{
                                        p: 3,
                                        textAlign: "center",
                                        bgcolor: "background.paper",
                                    }}
                                >
                                    <Typography variant="body1" color="text.secondary">
                                        No cameras detected
                                    </Typography>
                                    <Typography
                                        variant="caption"
                                        color="text.disabled"
                                        sx={{ mt: 1, display: "block" }}
                                    >
                                        Click refresh to scan for available cameras
                                    </Typography>
                                </Box>
                            }
                        />
                    ) : (
                        <>
                            {/* Group cameras by status for better organization */}
                            {isConnectedToCameras && (
                                <TreeItem
                                    itemId="cameras-connected"
                                    label={
                                        <Typography variant="subtitle2" sx={{ py: 0.5 }}>
                                            Connected Cameras
                                        </Typography>
                                    }
                                >
                                    {cameras
                                        .filter((cam) => cam.status === "CONNECTED")
                                        .map((camera) => (
                                            <CameraTreeItem
                                                key={camera.cameraId}
                                                camera={camera}
                                                isConfigExpanded={expandedConfigs.has(
                                                    camera.cameraId
                                                )}
                                                onToggleConfig={() =>
                                                    toggleConfig(camera.cameraId)
                                                }
                                                onConfigChange={handleConfigChange}
                                            />
                                        ))}
                                </TreeItem>
                            )}

                            <TreeItem
                                itemId="cameras-available"
                                label={
                                    <Typography variant="subtitle2" sx={{ py: 0.5 }}>
                                        Available Cameras
                                    </Typography>
                                }
                            >
                                {cameras
                                    .filter((cam) => cam.status !== "CONNECTED")
                                    .map((camera) => (
                                        <CameraTreeItem
                                            key={camera.cameraId}
                                            camera={camera}
                                            isConfigExpanded={expandedConfigs.has(
                                                camera.cameraId
                                            )}
                                            onToggleConfig={() =>
                                                toggleConfig(camera.cameraId)
                                            }
                                            onConfigChange={handleConfigChange}
                                        />
                                    ))}
                            </TreeItem>
                        </>
                    )}
                </TreeItem>
            </SimpleTreeView>
        </Paper>
    );
};
