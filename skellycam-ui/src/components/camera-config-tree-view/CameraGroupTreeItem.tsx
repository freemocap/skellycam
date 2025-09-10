import React from "react";
import { Box, Typography } from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import { CameraTreeItem } from "./CameraTreeItem";
import { CameraDevice } from "@/store/slices/cameras/cameras-types";

interface CameraGroupTreeItemProps {
    groupId: string;
    title: string;
    cameras: CameraDevice[];
    icon?: React.ReactNode;
    expandedItems?: string[];
}

export const CameraGroupTreeItem: React.FC<CameraGroupTreeItemProps> = ({
                                                                            groupId,
                                                                            title,
                                                                            cameras,
                                                                            icon,
                                                                            expandedItems,
                                                                        }) => {
    return (
        <TreeItem
            itemId={groupId}
            label={
                <Box sx={{ display: "flex", alignItems: "center", py: 0.5 }}>
                    {icon}
                    <Typography variant="subtitle2" sx={{ ml: 1 }}>
                        {title} ({cameras.length})
                    </Typography>
                </Box>
            }
        >
            {cameras.map((camera: CameraDevice) => (
                <CameraTreeItem
                    key={camera.cameraId}
                    camera={camera}
                    isExpanded={expandedItems.includes(`camera-${camera.cameraId}`)}
                />
            ))}
        </TreeItem>
    );
};
