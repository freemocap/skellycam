import {Box, CircularProgress, Typography} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import ErrorIcon from '@mui/icons-material/Error';
import {usePythonServerContext} from "@/context/python-server-context/PythonServerContext";
import {ServerStatus} from "@/context/python-server-context/usePythonServer";

export const getStatusIcon = (serverStatus: ServerStatus) => {
    switch (serverStatus) {
        case 'alive':
            return <CheckIcon sx={{color: 'green', fontSize: '16px'}}/>;
        case 'spawning':
            return <CircularProgress size={14} sx={{color: 'orange'}}/>;
        case 'error':
            return <ErrorIcon sx={{color: 'red', fontSize: '16px'}}/>;
        default:
            return <CloseIcon fontSize="small" sx={{color: 'red'}}/>;
    }
};

export const getStatusBorderColor = (serverStatus: ServerStatus) => {
    switch (serverStatus) {
        case 'alive':
            return 'rgba(0, 255, 255, 0.1)';
        case 'spawning':
            return 'rgba(255, 165, 0, 0.1)';

        case 'shutting-down':
            return 'rgba(105, 0, 255,0.1)';
        case 'error':
            return 'rgba(255, 0, 0, 0.1)';
        case 'not-connected':
            return 'rgba(255, 255, 255, 0.1)';
        default:
            return 'rgba(255, 255, 255, 0.1)';
    }
};

export const getServerStatusBackgroundColor = (serverStatus: ServerStatus) => {
    switch (serverStatus) {
        case 'alive':
            return 'rgba(0, 255, 255, 0.5)';
        case 'spawning':
            return 'rgba(255, 165, 0, 0.5)';

        case 'shutting-down':
            return 'rgba(105, 0, 255,0.5)';
        case 'error':
            return 'rgba(255, 0, 0, 0.5)';
        case 'not-connected':
            return 'rgba(255, 255, 255, 0.1)';
        default:
            return 'rgba(255, 255, 255, 0.1)';
    }
};

export const ServerConnectionStatus = () => {
    const {serverStatus, errorMessage, stopPythonServer, startPythonServer} = usePythonServerContext();


    const handleClick = () => {
        if (serverStatus === 'alive' || serverStatus === 'spawning') {
            console.log('Stopping Python Server');
            stopPythonServer();
        } else {
            console.log('Stopping Python Server');
            startPythonServer(null)
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
                    backgroundColor: getStatusBorderColor(serverStatus),
                    borderColor: getServerStatusBackgroundColor(serverStatus),
                    width: '24px',
                    height: '24px',
                    marginRight: '8px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}>
                    {getStatusIcon(serverStatus)}
                </Box>
                Python Server: {serverStatus}
            </Typography>
            {errorMessage && (
                <Typography variant="caption" sx={{color: 'error.main', pl: 5, mt: 0.5}}>
                    {errorMessage}
                </Typography>
            )}
        </Box>
    );
};
