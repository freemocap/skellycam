import React, { useState } from "react";
import { Box, IconButton, Tooltip, Typography, Chip, useTheme } from "@mui/material";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import VideocamIcon from "@mui/icons-material/Videocam";
import SettingsIcon from "@mui/icons-material/Settings";

import { CameraConfigTreeSection } from "./CameraConfigTreeSection";
import { useAppDispatch } from "@/store";
import { cameraSelectionToggled } from "@/store/slices/cameras/cameras-slice";
import { CameraDevice } from "@/store/slices/cameras/cameras-types";

interface CameraTreeItemProps {
    camera: CameraDevice;
}

export const CameraTreeItem: React.FC<CameraTreeItemProps> = ({ camera }) => {
    const dispatch = useAppDispatch();
    const theme = useTheme();
    const [isConfigExpanded, setIsConfigExpanded] = useState<boolean>(false);

    const handleToggleSelection = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(cameraSelectionToggled(camera.cameraId));
    };

    const handleToggleConfig = (e: React.MouseEvent): void => {
        e.stopPropagation();
        setIsConfigExpanded(!isConfigExpanded);
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
                    <IconButton size="small" onClick={handleToggleSelection} sx={{ mr: 1 }}>
                        {camera.selected ? (
                            <CheckCircleIcon color="primary" />
                        ) : (
                            <RadioButtonUncheckedIcon />
                        )}
                    </IconButton>

                    <VideocamIcon sx={{ mr: 1, color: getStatusColor() }} />

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
            {camera.selected && isConfigExpanded && (
                <CameraConfigTreeSection camera={camera} />
            )}
        </TreeItem>
    );
};
