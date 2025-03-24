// skellycam-ui/src/components/config-views/camera-config/CameraListItem.tsx
import { Box, Checkbox, IconButton, ListItem, ListItemIcon, ListItemText, Typography } from "@mui/material";
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { SerializedMediaDeviceInfo } from "@/store/slices/cameras-slices/cameraDevicesSlice";
import * as React from "react";

interface CameraListItemProps {
    device: SerializedMediaDeviceInfo;
    isLast: boolean;
    isConfigExpanded: boolean;
    onToggleSelect: () => void;
    onToggleConfig: () => void;
}

export const CameraListItem: React.FC<CameraListItemProps> = ({
    device,
    isLast,
    isConfigExpanded,
    onToggleSelect,
    onToggleConfig
}) => (
    <ListItem
        sx={{
            '&:hover': {
                bgcolor: 'action.hover',
            },
            borderBottom: isLast ? 0 : 1,
            borderColor: 'divider',
        }}
    >
        <ListItemIcon>
            <Checkbox
                edge="start"
                checked={device.selected || false}
                onChange={onToggleSelect}
                color="primary"
            />
        </ListItemIcon>
        <ListItemText
            primary={
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Typography
                        component="span"
                        variant="body2"
                        color="primary.main"
                        sx={{ mr: 1, fontWeight: 600 }}
                    >
                        Camera {device.index}
                    </Typography>
                    <Typography
                        component="span"
                        variant="body2"
                        color="text.secondary"
                    >
                        {device.label || `Unknown Device ${device.index}`}
                    </Typography>
                </Box>
            }
        />
        {device.selected && (
            <IconButton
                size="small"
                onClick={onToggleConfig}
            >
                {isConfigExpanded
                    ? <KeyboardArrowUpIcon />
                    : <KeyboardArrowDownIcon />}
            </IconButton>
        )}
    </ListItem>
);
