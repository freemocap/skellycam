import React from 'react';
import {Box, Typography} from '@mui/material';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

const WebsocketConnectionStatus = () => {
    const {isConnected} = useWebSocketContext();

    return (
        <Box sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            padding: '20px',
            flexDirection: 'column',
            color: '#dadada'
        }}>
            <Typography variant="h6">
                Websocket: {isConnected ? 'connected ✔️' : 'disconnected❌'}
            </Typography>
        </Box>
    );
};

export default WebsocketConnectionStatus
