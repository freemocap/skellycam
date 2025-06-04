import React from 'react';
import {Box, Typography} from '@mui/material';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

const WebsocketConnectionStatus = () => {
    const {isConnected} = useWebSocketContext();

    return (
        <Box sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            padding: '10px',
            flexDirection: 'column',
            pl: 4,
            color: '#dadada'
        }}>
            <Typography variant="body1">
                Websocket: {isConnected ? 'connected ✔️' : 'disconnected❌'}
            </Typography>
        </Box>
    );
};

export default WebsocketConnectionStatus
