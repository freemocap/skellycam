import {Box, Tooltip, Typography} from "@mui/material";
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import {usePythonServerContext} from "@/context/python-server-context/PythonServerContext";

export const ServerConnectionStatus = () => {
    const { isRunning: isPythonRunning } = usePythonServerContext();


    return (

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
                        mt: 1,
                    }}
                >
                    <Box sx={{
                        border: '1px solid rgba(255, 255, 255, 0.3)',
                        backgroundColor: isPythonRunning ? 'rgba(0, 255, 255, 0.1)' : 'rgba(255, 0, 0, 0.1)',
                        borderColor: isPythonRunning ? 'rgba(0, 255, 255, 0.5)' : 'rgba(255, 0, 0, 0.5)',

                        width: '24px',
                        height: '24px',
                        marginRight: '8px',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}>
                        {isPythonRunning ? (
                            <CheckIcon sx={{ color: 'green', fontSize: '16px' }} />
                        ) : (
                            <CloseIcon fontSize="small" sx={{ color: 'red' }} />
                        )}
                    </Box>
                    Python Server: {isPythonRunning ? 'running' : 'stopped'}
                </Typography>
            </Box>
    );
};
