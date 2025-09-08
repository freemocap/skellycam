import React from 'react';
import { Box, Typography } from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import { useAppSelector } from "@/store";
import { selectIsWebSocketConnected, selectWebSocketStatus } from "@/store/slices/websocket/websocket-selectors";
import { websocketService } from "@/services/websocket/websocket-service";

const WebsocketConnectionStatus: React.FC = () => {
    const isConnected = useAppSelector(selectIsWebSocketConnected);
    const connectionStatus = useAppSelector(selectWebSocketStatus);

    const handleToggleConnection = () => {
        if (isConnected) {
            console.log('Toggling WebSocket: disconnecting');
            websocketService.disconnect();
        } else {
            console.log('Toggling WebSocket: connecting');
            websocketService.connect();
        }
    };

    return (
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                padding: '10px',
                flexDirection: 'column',
                pl: 4,
                color: '#dadada',
                cursor: 'pointer',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                ':hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    borderColor: 'rgba(255, 255, 255, 0.2)',
                },
            }}
            onClick={handleToggleConnection}
        >
            <Typography
                variant="body1"
                component="div"
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                }}
            >
                <Box sx={{
                    border: '1px solid rgba(255, 255, 255, 0.3)',
                    width: '24px',
                    height: '24px',
                    marginRight: '8px',
                    cursor: 'pointer',
                    borderRadius: '4px',
                    transition: 'background-color 0.3s, border-color 0.3s',
                    backgroundColor: isConnected ? 'rgba(0, 255, 255, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                    borderColor: isConnected ? 'rgba(0, 255, 255, 0.5)' : 'rgba(255, 0, 0, 0.5)',
                    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px',
                    justifyContent: 'center',
                    '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.05)',
                        borderColor: 'rgba(255, 255, 255, 0.2)',
                    },
                }}>
                    {isConnected ? (
                        <CheckIcon sx={{ color: 'green' }} />
                    ) : (
                        <CloseIcon fontSize="small" sx={{ color: 'red' }} />
                    )}
                </Box>
                WebSocket: {connectionStatus === 'connecting' || connectionStatus === 'reconnecting'
                ? connectionStatus
                : isConnected ? 'connected' : 'disconnected'}
            </Typography>
        </Box>
    );
};

export default WebsocketConnectionStatus;
