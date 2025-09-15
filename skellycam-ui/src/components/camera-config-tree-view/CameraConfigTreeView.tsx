import React, { useEffect, useState } from "react";
import {
    Box,
    Paper,
    Typography,
    useTheme,
} from "@mui/material";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ChevronRight from "@mui/icons-material/ChevronRight";
import VideoCameraFrontIcon from '@mui/icons-material/VideoCameraFront';

import { CameraConfigTreeViewHeader } from "./CameraConfigTreeViewHeader";
import { CameraGroupTreeItem } from "./CameraGroupTreeItem";
import { NoCamerasPlaceholder } from "./NoCamerasPlaceholder";
import {
    cameraSelectionToggled,
    selectIsServerAlive,
    selectIsWebSocketConnected,
    useAppDispatch,
    useAppSelector,
    selectAllCameras,
    selectCameraLoadingState,
    selectCameraConnectionStatus,
    selectSelectedCameras,
    detectCameras,
    CameraDevice
} from "@/store";


export const CameraConfigTreeView: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    // Redux state
    const cameras = useAppSelector(selectAllCameras);
    const isLoading = useAppSelector(selectCameraLoadingState);
    const connectionStatus = useAppSelector(selectCameraConnectionStatus);
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const isWebSocketConnected = useAppSelector(selectIsWebSocketConnected);
    const isServerAlive = useAppSelector(selectIsServerAlive);

    // Local state
    const [expandedItems, setExpandedItems] = useState<string[]>([
        "cameras-root",
        "cameras-connected",
        "cameras-available"
    ]);
    const [isPaused, setIsPaused] = useState<boolean>(false);

    // Group cameras by status
    const connectedCameras = cameras.filter((cam: CameraDevice) => cam.status === "CONNECTED");
    const availableCameras = cameras.filter((cam: CameraDevice) => cam.status !== "CONNECTED");
    const isConnectedToCameras = connectionStatus === "connected";
    const hasSelectedCameras = selectedCameras.length > 0;

    // Initial camera detection
    useEffect(() => {
        if (isWebSocketConnected && isServerAlive && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [isWebSocketConnected, isServerAlive, cameras.length, dispatch]);

    const handleExpandedItemsChange = (
        event: React.SyntheticEvent,
        itemIds: string[]
    ): void => {
        setExpandedItems(itemIds);
    };

    const handlePauseToggle = (): void => {
        setIsPaused(!isPaused);
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
                    collapseIcon: ExpandMore,
                    expandIcon: ChevronRight,
                }}
            >
                <TreeItem
                    itemId="cameras-root"
                    label={
                        <CameraConfigTreeViewHeader
                            cameraCount={cameras.length}
                            isConnected={isConnectedToCameras}
                            isLoading={isLoading}
                            isPaused={isPaused}
                            onPauseToggle={handlePauseToggle}
                            hasSelectedCameras={hasSelectedCameras}
                        />
                    }
                >
                    {cameras.length === 0 ? (
                        <NoCamerasPlaceholder />
                    ) : (
                        <>
                            {/* Connected Cameras Group */}
                            {isConnectedToCameras && connectedCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-connected"
                                    title="Connected Cameras"
                                    cameras={connectedCameras}
                                    icon={<VideoCameraFrontIcon color="success" />}
                                    expandedItems={expandedItems}
                                />
                            )}

                            {/* Available Cameras Group */}
                            {availableCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-available"
                                    title="Available Cameras"
                                    cameras={availableCameras}
                                    icon={<VideoCameraFrontIcon color="info" />}
                                    expandedItems={expandedItems}
                                />
                            )}
                        </>
                    )}
                </TreeItem>
            </SimpleTreeView>
        </Paper>
    );
};
