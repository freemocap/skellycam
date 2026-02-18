// skellycam-ui/src/components/ui-components/LeftSidePanelContent.tsx
import * as React from 'react';
import Box from "@mui/material/Box";
import {IconButton, List, ListItem, useTheme} from "@mui/material";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";
import ThemeToggle from "@/components/ui-components/ThemeToggle";
import HomeIcon from '@mui/icons-material/Home';
import {useLocation, useNavigate} from "react-router-dom";
import VideocamIcon from '@mui/icons-material/Videocam';
import SlideshowIcon from '@mui/icons-material/Slideshow';
import {CameraConfigTreeView} from "@/components/camera-config-tree-view/CameraConfigTreeView";
import {ServerConnectionStatus} from "@/components/ServerConnectionStatus";

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
            overflowY: 'auto',
            overflowX: 'hidden',
            ...scrollbarStyles
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
                            color: theme.palette.text.primary
                        }}
                    >
                        SkellyCam 💀📸
                    </Box>

                    <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                        <IconButton
                            size="small"
                            onClick={() => navigate('/')}
                            sx={{
                                padding: '4px',
                                color: location.pathname === '/' ? theme.palette.success.main : theme.palette.text.secondary,
                            }}
                        >
                            <HomeIcon sx={{ fontSize: 18 }} />
                        </IconButton>

                        {/* Cameras nav — labeled button */}
                        <Box
                            onClick={() => navigate('/cameras')}
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                                px: 1,
                                py: 0.35,
                                borderRadius: 1,
                                cursor: 'pointer',
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                transition: 'all 0.15s ease',
                                ...(location.pathname === '/cameras'
                                    ? {
                                        color: '#fff',
                                        backgroundColor: theme.palette.success.main,
                                    }
                                    : {
                                        color: theme.palette.text.secondary,
                                        border: `1px solid ${theme.palette.divider}`,
                                        '&:hover': {
                                            borderColor: theme.palette.success.main,
                                            color: theme.palette.success.main,
                                        },
                                    }),
                            }}
                        >
                            <VideocamIcon sx={{ fontSize: 15 }} />
                            Cameras
                        </Box>

                        {/* Playback nav — labeled button */}
                        <Box
                            onClick={() => navigate('/playback')}
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                                px: 1,
                                py: 0.35,
                                borderRadius: 1,
                                cursor: 'pointer',
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                transition: 'all 0.15s ease',
                                ...(location.pathname === '/playback'
                                    ? {
                                        color: '#fff',
                                        backgroundColor: theme.palette.success.main,
                                    }
                                    : {
                                        color: theme.palette.text.secondary,
                                        border: `1px solid ${theme.palette.divider}`,
                                        '&:hover': {
                                            borderColor: theme.palette.success.main,
                                            color: theme.palette.success.main,
                                        },
                                    }),
                            }}
                        >
                            <SlideshowIcon sx={{ fontSize: 15 }} />
                            Videos
                        </Box>

                        <ThemeToggle/>
                    </Box>
                </ListItem>
            </List>

            {/* Server Settings - Compact */}
            <ServerConnectionStatus/>

            {/* Main Content Area */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5,
                pt: 0.5,
                pb: 2,
            }}>
                <RecordingInfoPanel/>
                <CameraConfigTreeView/>
            </Box>
        </Box>
    );
}
