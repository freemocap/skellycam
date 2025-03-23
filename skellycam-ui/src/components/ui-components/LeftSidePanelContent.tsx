import * as React from 'react';
import Box from "@mui/material/Box";
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {List, ListItem, Paper} from "@mui/material";
import WebsocketConnectionStatus from "@/components/WebsocketConnectionStatus";
import {AvailableCamerasView} from "@/components/config-views/AvailableCamerasView";
import {ConnectToCamerasButton} from "@/components/ConnectToCamerasButton";
import {RecordingPanel} from "@/components/RecordingPanel";


const item = {
    py: '2px',
    px: 3,
    color: extendedPaperbaseTheme.palette.primary.contrastText,
    '&:hover, &:focus': {
        bgcolor: 'rgba(255, 255, 255, 0.08)',
    },
};

const itemCategory = {
    boxShadow: '0 -1px 0 rgb(255,255,255,0.1) inset',
    py: 1.5,
    px: 3,
};


export const LeftSidePanelContent = () => {
    return (
        <Box sx={{
            width: '100%',
            height: '100%',
            backgroundColor: extendedPaperbaseTheme.palette.primary.dark,
            color: extendedPaperbaseTheme.palette.primary.contrastText,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
        }}>
            <List disablePadding>
                <ListItem sx={{...item, ...itemCategory, fontSize: 22, color: '#fafafa'}}>
                    SkellyCam💀📸
                </ListItem>
            </List>

            <Box sx={{
                flex: 1,
                overflowY: 'auto',
                overflowX: 'hidden',
                '&::-webkit-scrollbar': {
                    width: '8px',
                    backgroundColor: 'transparent',
                },
                '&::-webkit-scrollbar-thumb': {
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                    borderRadius: '4px',
                    '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.3)',
                    },
                },
                '&::-webkit-scrollbar-track': {
                    backgroundColor: 'transparent',
                },
                // For Firefox
                scrollbarWidth: 'thin',
                scrollbarColor: 'rgba(255, 255, 255, 0.2) transparent',
            }}>
                <WebsocketConnectionStatus/>
                <RecordingPanel/>
                <ConnectToCamerasButton/>
                <AvailableCamerasView/>
                <Paper/>
            </Box>
        </Box>
    );
}

