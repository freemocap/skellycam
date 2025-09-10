import React, { useEffect, useState } from "react";
import {
    Box,
    Paper,
    Typography,
    useTheme,
} from "@mui/material";
import { SimpleTreeView } from "@mui/x-tree-view/SimpleTreeView";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import VideocamIcon from "@mui/icons-material/Videocam";

import { CameraConfigTreeViewHeader } from "./CameraConfigTreeViewHeader";
import { CameraGroupTreeItem } from "./CameraGroupTreeItem";
import { NoCamerasPlaceholder } from "./NoCamerasPlaceholder";
import {
    selectIsServerAlive,
    selectIsWebSocketConnected,
    useAppDispatch,
    useAppSelector
} from "@/store";
import {
    selectAllCameras,
    selectCameraLoadingState,
    selectCameraConnectionStatus,
    selectSelectedCameras,
} from "@/store/slices/cameras/cameras-selectors";
import {
    detectCameras,
} from "@/store/slices/cameras/cameras-thunks";
import {
    allCamerasSelected,
    allCamerasDeselected,
} from "@/store/slices/cameras/cameras-slice";
import { CameraDevice } from "@/store/slices/cameras/cameras-types";

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

    // Expand/Collapse all handlers
    const handleExpandAll = (): void => {
        const allItemIds = [
            "cameras-root",
            "cameras-connected",
            "cameras-available",
            ...cameras.map(cam => `camera-${cam.cameraId}`),
            ...cameras.map(cam => `camera-${cam.cameraId}-config`)
        ];
        setExpandedItems(allItemIds);
    };

    const handleCollapseAll = (): void => {
        setExpandedItems(["cameras-root"]); // Keep root expanded
    };

    // Select/Deselect all handlers
    const handleSelectAll = (): void => {
        // Toggle selection for all cameras that are not selected
        cameras.forEach((camera: CameraDevice) => {
            if (!camera.selected) {
                dispatch(cameraSelectionToggled(camera.cameraId));
            }
        });
    };

    const handleDeselectAll = (): void => {
        // Toggle selection for all cameras that are selected
        cameras.forEach((camera: CameraDevice) => {
            if (camera.selected) {
                dispatch(cameraSelectionToggled(camera.cameraId));
            }
        });
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
                        <CameraConfigTreeViewHeader
                            cameraCount={cameras.length}
                            isConnected={isConnectedToCameras}
                            isLoading={isLoading}
                            isPaused={isPaused}
                            onPauseToggle={handlePauseToggle}
                            onExpandAll={handleExpandAll}
                            onCollapseAll={handleCollapseAll}
                            onSelectAll={handleSelectAll}
                            onDeselectAll={handleDeselectAll}
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
                                    icon={<VideocamIcon color="success" />}
                                    expandedItems={expandedItems}
                                />
                            )}

                            {/* Available Cameras Group */}
                            {availableCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-available"
                                    title="Available Cameras"
                                    cameras={availableCameras}
                                    icon={<VideocamIcon color="info" />}
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
