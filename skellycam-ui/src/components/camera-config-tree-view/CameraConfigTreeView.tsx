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
} from "@/store/slices/cameras/cameras-selectors";
import { detectCameras } from "@/store/slices/cameras/cameras-thunks";
import { CameraDevice } from "@/store/slices/cameras/cameras-types";

export const CameraConfigTreeView: React.FC = () => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    // Redux state
    const cameras = useAppSelector(selectAllCameras);
    const isLoading = useAppSelector(selectCameraLoadingState);
    const connectionStatus = useAppSelector(selectCameraConnectionStatus);
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
                                />
                            )}

                            {/* Available Cameras Group */}
                            {availableCameras.length > 0 && (
                                <CameraGroupTreeItem
                                    groupId="cameras-available"
                                    title="Available Cameras"
                                    cameras={availableCameras}
                                    icon={<VideocamIcon color="info" />}
                                />
                            )}
                        </>
                    )}
                </TreeItem>
            </SimpleTreeView>
        </Paper>
    );
};
