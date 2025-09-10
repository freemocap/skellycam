// skellycam-ui/src/components/ui-components/LeftSidePanelContent.tsx
import * as React from 'react';
import Box from "@mui/material/Box";
import {IconButton, List, ListItem, useTheme} from "@mui/material";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";
import ThemeToggle from "@/components/ui-components/ThemeToggle";
import HomeIcon from '@mui/icons-material/Home';
import {useLocation, useNavigate} from "react-router-dom";
import VideocamIcon from '@mui/icons-material/Videocam';
import {VideoFolderPanel} from "@/components/video-folder-panel/VideoFolderPanel";
import {ServerSettingsPanel} from '../server-settings-panel/ServerSettingsPanel';
import {CameraConfigTreeView} from "@/components/camera-config-tree-view/CameraConfigTreeView";

// Extract reusable scrollbar styles
const scrollbarStyles = {
    '&::-webkit-scrollbar': {
        width: '6px',
        backgroundColor: 'transparent',
    },
    '&::-webkit-scrollbar-thumb': {
        backgroundColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
            ? 'rgba(255, 255, 255, 0.2)'
            : 'rgba(0, 0, 0, 0.2)',
        borderRadius: '3px',
        '&:hover': {
            backgroundColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
                ? 'rgba(255, 255, 255, 0.3)'
                : 'rgba(0, 0, 0, 0.3)',
        },
    },
    '&::-webkit-scrollbar-track': {
        backgroundColor: 'transparent',
    },
    scrollbarWidth: 'thin',
    scrollbarColor: (theme: { palette: { mode: string; }; }) => theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.2) transparent'
        : 'rgba(0, 0, 0, 0.2) transparent',
};

export const LeftSidePanelContent = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const location = useLocation();

    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            backgroundColor: theme.palette.mode === 'dark'
                ? theme.palette.background.paper
                : theme.palette.grey[50],
            color: theme.palette.text.primary,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
        }}>
            {/* Header */}
            <List disablePadding>
                <ListItem
                    sx={{
                        borderBottom: theme.palette.mode === 'dark'
                            ? '1px solid rgba(255,255,255,0.08)'
                            : '1px solid rgba(0,0,0,0.08)',
                        py: 0.75,
                        px: 1.5,
                        minHeight: 40,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                    }}
                >
                    <Box
                        component="span"
                        sx={{
                            fontSize: 16,
                            fontWeight: 600,
                            color: theme.palette.primary.main
                        }}
                    >
                        SkellyCam 💀📸
                    </Box>

                    <Box sx={{display: 'flex', alignItems: 'center', gap: 0.25}}>
                        <IconButton
                            size="small"
                            onClick={() => navigate('/')}
                            sx={{
                                padding: '4px',
                                color: location.pathname === '/' ? theme.palette.primary.main : theme.palette.text.secondary
                            }}
                        >
                            <HomeIcon sx={{ fontSize: 18 }} />
                        </IconButton>

                        <IconButton
                            size="small"
                            onClick={() => navigate('/cameras')}
                            sx={{
                                padding: '4px',
                                color: location.pathname === '/cameras' ? theme.palette.primary.main : theme.palette.text.secondary
                            }}
                        >
                            <VideocamIcon sx={{ fontSize: 18 }} />
                        </IconButton>

                        <ThemeToggle/>
                    </Box>
                </ListItem>
            </List>

            {/* Server Settings - Compact */}
            <ServerSettingsPanel/>

            {/* Video Panel for Videos Page */}
            {location.pathname === '/videos' && (
                <Box sx={{
                    flex: 0.3,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    borderTop: '1px solid',
                    borderColor: theme.palette.divider,
                    ...scrollbarStyles
                }}>
                    <VideoFolderPanel/>
                </Box>
            )}

            {/* Main Content Area */}
            <Box sx={{
                flex: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5,
                pt: 0.5,
                ...scrollbarStyles
            }}>
                <RecordingInfoPanel/>
                <CameraConfigTreeView/>
            </Box>
        </Box>
    );
}
