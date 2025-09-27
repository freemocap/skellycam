// components/WebsocketConnectionStatus.tsx
import React from 'react';
import { Box, Typography } from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import CircularProgress from '@mui/material/CircularProgress';
import {
    useAppDispatch,
    useAppSelector,
    selectIsWebSocketConnected,
    selectWebSocketStatus,
    selectIsServerConnected,
    websocketStatusChanged,
} from "@/store";
import {useWebSocket} from "@/services/websocket/WebsocketContextProvider";

export const WebsocketConnectionStatus: React.FC = () => {

    const wsStatus = useAppSelector(selectWebSocketStatus);
    const isServerConnected = useAppSelector(selectIsServerConnected);

    const handleToggleConnection = () => {
        if (!isServerConnected) {
            console.log('Cannot toggle WebSocket: Server not connected');
            return;
        }

    };

    const getStatusIcon = () => {
        switch (wsStatus) {
            case 'connected':
                return <CheckIcon sx={{ color: 'green' }} />;
            case 'connecting':
            case 'reconnecting':
                return <CircularProgress size={14} sx={{ color: 'orange' }} />;
            default:
                return <CloseIcon fontSize="small" sx={{ color: 'red' }} />;
        }
    };

    const getStatusColor = () => {
        if (!isServerConnected) {
            return {
                bg: 'rgba(128, 128, 128, 0.1)',
                border: 'rgba(128, 128, 128, 0.3)'
            };
        }

        switch (wsStatus) {
            case 'connected':
                return {
                    bg: 'rgba(0, 255, 255, 0.1)',
                    border: 'rgba(0, 255, 255, 0.5)'
                };
            case 'connecting':
            case 'reconnecting':
                return {
                    bg: 'rgba(255, 165, 0, 0.1)',
                    border: 'rgba(255, 165, 0, 0.5)'
                };
            default:
                return {
                    bg: 'rgba(255, 0, 0, 0.1)',
                    border: 'rgba(255, 0, 0, 0.5)'
                };
        }
    };

    const colors = getStatusColor();

    return (
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                padding: '10px',
                flexDirection: 'column',
                pl: 4,
                color: '#dadada',
                cursor: isServerConnected ? 'pointer' : 'not-allowed',
                opacity: isServerConnected ? 1 : 0.6,
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                ':hover': isServerConnected ? {
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    borderColor: 'rgba(255, 255, 255, 0.2)',
                } : {},
            }}
            onClick={isServerConnected ? handleToggleConnection : undefined}
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
                    borderRadius: '4px',
                    transition: 'background-color 0.3s, border-color 0.3s',
                    backgroundColor: colors.bg,
                    borderColor: colors.border,
                    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}>
                    {getStatusIcon()}
                </Box>
                WebSocket: {wsStatus}
            </Typography>
            {!isServerConnected && (
                <Typography variant="caption" sx={{ color: 'text.secondary', pl: 5, mt: 0.5 }}>
                    Server must be connected first
                </Typography>
            )}
        </Box>
    );
};

export default WebsocketConnectionStatus;
