import {Box, Tooltip, Typography} from "@mui/material";
import {urlService} from "@/services/urlService";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import { useState, useEffect } from "react";

const ServerConnectionStatus = () => {
    const [isHttpConnected, setIsHttpConnected] = useState(false);
    const [isWsConnected, setIsWsConnected] = useState(false);
    const httpUrl = urlService.getApiUrl('');
    const wsUrl = urlService.getWebSocketUrl();

    // In a real implementation, you would check actual connection status
    // For now, we'll simulate connection checks
    useEffect(() => {
        const checkConnections = () => {
            // Simulate HTTP connection check
            fetch(httpUrl + '/health', { method: 'GET', mode: 'no-cors' })
                .then(() => setIsHttpConnected(true))
                .catch(() => setIsHttpConnected(false));
        };

        checkConnections();
        const interval = setInterval(checkConnections, 5000); // Check every 5 seconds
        return () => clearInterval(interval);
    }, [httpUrl]);

    return (
        <Tooltip 
            title={
                <Box>
                    <Typography variant="body2">HTTP URL: {httpUrl}</Typography>
                    <Typography variant="body2">WebSocket URL: {wsUrl}</Typography>
                </Box>
            } 
            placement="bottom-start" 
            arrow
        >
            <Box
                sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    padding: '10px',
                    pl: 4,
                    color: '#dadada',
                }}
            >
                <Typography
                    variant="body1"
                    component="div"
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        mb: 0.5,
                    }}
                >
                    <Box sx={{
                        border: '1px solid rgba(255, 255, 255, 0.3)',
                        backgroundColor: isHttpConnected ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                        width: '24px',
                        height: '24px',
                        marginRight: '8px',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}>
                        {isHttpConnected ? (
                            <CheckIcon sx={{ color: 'green', fontSize: '16px' }} />
                        ) : (
                            <CloseIcon fontSize="small" sx={{ color: 'red' }} />
                        )}
                    </Box>
                    HTTP: {isHttpConnected ? 'connected' : 'disconnected'}
                </Typography>
                
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
                        backgroundColor: isWsConnected ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                        width: '24px',
                        height: '24px',
                        marginRight: '8px',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}>
                        {isWsConnected ? (
                            <CheckIcon sx={{ color: 'green', fontSize: '16px' }} />
                        ) : (
                            <CloseIcon fontSize="small" sx={{ color: 'red' }} />
                        )}
                    </Box>
                    WebSocket: {isWsConnected ? 'connected' : 'disconnected'}
                </Typography>
            </Box>
        </Tooltip>
    );
};

export default ServerConnectionStatus;