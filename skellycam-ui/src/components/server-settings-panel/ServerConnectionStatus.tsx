// components/ServerConnectionStatus.tsx
import React from 'react';
import { Box, CircularProgress, Typography } from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import ErrorIcon from '@mui/icons-material/Error';
import {
    useAppDispatch,
    useAppSelector,
    selectConnectionStatus,
    selectConnectionError,
    selectHasManagedServer,
    selectCanConnect,
    startManagedServer,
    stopManagedServer,
    connectToExternalServer,
    disconnectFromServer,
} from "@/store";
import { useElectronIPC } from "@/services/electron-ipc/electron-ipc";

const getStatusIcon = (status: string) => {
    switch (status) {
        case 'connected':
            return <CheckIcon sx={{ color: 'green', fontSize: '16px' }} />;
        case 'connecting':
        case 'disconnecting':
            return <CircularProgress size={14} sx={{ color: 'orange' }} />;
        case 'error':
            return <ErrorIcon sx={{ color: 'red', fontSize: '16px' }} />;
        default:
            return <CloseIcon fontSize="small" sx={{ color: 'red' }} />;
    }
};

const getStatusBorderColor = (status: string) => {
    switch (status) {
        case 'connected':
            return 'rgba(0, 255, 255, 0.1)';
        case 'connecting':
        case 'disconnecting':
            return 'rgba(255, 165, 0, 0.1)';
        case 'error':
            return 'rgba(255, 0, 0, 0.1)';
        default:
            return 'rgba(255, 255, 255, 0.1)';
    }
};

const getStatusBackgroundColor = (status: string) => {
    switch (status) {
        case 'connected':
            return 'rgba(0, 255, 255, 0.5)';
        case 'connecting':
        case 'disconnecting':
            return 'rgba(255, 165, 0, 0.5)';
        case 'error':
            return 'rgba(255, 0, 0, 0.5)';
        default:
            return 'rgba(255, 255, 255, 0.1)';
    }
};

export const ServerConnectionStatus: React.FC = () => {
    const dispatch = useAppDispatch();
    const { isElectron } = useElectronIPC();

    const connectionStatus = useAppSelector(selectConnectionStatus);
    const connectionError = useAppSelector(selectConnectionError);
    const hasManagedServer = useAppSelector(selectHasManagedServer);
    const canConnect = useAppSelector(selectCanConnect);

    const handleClick = () => {
        if (connectionStatus === 'connected' || connectionStatus === 'connecting') {
            // Stop or disconnect based on whether it's managed
            if (hasManagedServer) {
                console.log('Stopping managed Python server');
                dispatch(stopManagedServer());
            } else {
                console.log('Disconnecting from external server');
                dispatch(disconnectFromServer());
            }
        } else if (canConnect) {
            // Start or connect
            if (isElectron) {
                console.log('Starting managed Python server');
                dispatch(startManagedServer());
            } else {
                console.log('Connecting to external server');
                dispatch(connectToExternalServer());
            }
        }
    };

    const getStatusText = () => {
        if (connectionStatus === 'connecting') return 'connecting...';
        if (connectionStatus === 'disconnecting') return 'disconnecting...';
        if (connectionStatus === 'connected') {
            return hasManagedServer ? 'connected (managed)' : 'connected (external)';
        }
        return connectionStatus;
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
            onClick={handleClick}
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
                    backgroundColor: getStatusBorderColor(connectionStatus),
                    borderColor: getStatusBackgroundColor(connectionStatus),
                    width: '24px',
                    height: '24px',
                    marginRight: '8px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}>
                    {getStatusIcon(connectionStatus)}
                </Box>
                Python Server: {getStatusText()}
            </Typography>
            {connectionError && (
                <Typography variant="caption" sx={{ color: 'error.main', pl: 5, mt: 0.5 }}>
                    {connectionError}
                </Typography>
            )}
        </Box>
    );
};
