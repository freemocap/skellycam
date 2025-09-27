// components/ServerSettingsPanel.tsx
import React, {useEffect, useState} from 'react';
import {
    Alert,
    Box,
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    LinearProgress,
    Paper,
    SelectChangeEvent,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material';
import {
    ExpandMore as ExpandMoreIcon,
    PlayArrow as PlayArrowIcon,
    Settings as SettingsIcon,
    Stop as StopIcon,
    Storage as StorageIcon,
} from '@mui/icons-material';
import {styled} from '@mui/material/styles';
import {
    connectToServer,
    disconnectFromServer,
    refreshExecutableCandidates,
    selectAutoConnect,
    selectAutoSpawn,
    selectCanConnect,
    selectCanDisconnect,
    selectConnectionError,
    selectConnectionMode,
    selectConnectionStatus,
    selectExecutableCandidates,
    selectHasManagedServer,
    selectHttpUrl,
    selectIsRefreshingExecutables,
    selectIsServerConnected,
    selectIsServerTransitioning,
    selectIsWebSocketConnected,
    selectManagedProcess,
    selectPreferredExecutablePath,
    selectServerConfig,
    selectWebSocketStatus,
    selectWebSocketUrl,
    updateServerConfig,
    useAppDispatch,
    useAppSelector,
    websocketStatusChanged,
} from "@/store";
import {useElectronIPC} from "@/services/electron-ipc/electron-ipc";

const StatusDot = styled('span')<{ status: string }>(({ theme, status }) => {
    const getStatusColor = () => {
        switch (status) {
            case 'connected':
                return theme.palette.success.main;
            case 'connecting':
            case 'disconnecting':
                return theme.palette.warning.main;
            case 'error':
                return theme.palette.error.main;
            default:
                return theme.palette.grey[500];
        }
    };

    return {
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: getStatusColor(),
        display: 'inline-block',
        marginRight: theme.spacing(0.5),
    };
});

// External server connection dialog (unchanged)
const ConnectionDialog: React.FC<{
    open: boolean;
    onClose: () => void;
}> = ({ open, onClose }) => {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectServerConfig);
    const [host, setHost] = useState(config.host);
    const [port, setPort] = useState(config.port);

    const handleConnect = async () => {
        dispatch(updateServerConfig({ host, port }));
        try {
            await dispatch(connectToServer({
                mode: 'external',
                host,
                port
            })).unwrap();
            onClose();
        } catch (error) {
            console.error('Failed to connect to external server:', error);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Connect to External Server</DialogTitle>
            <DialogContent>
                <Stack spacing={2} sx={{ mt: 2 }}>
                    <TextField
                        label="Host"
                        value={host}
                        onChange={(e) => setHost(e.target.value)}
                        fullWidth
                        size="small"
                    />
                    <TextField
                        label="Port"
                        type="number"
                        value={port}
                        onChange={(e) => setPort(parseInt(e.target.value) || 8006)}
                        fullWidth
                        size="small"
                    />
                    <Typography variant="caption" color="text.secondary">
                        Connect to a SkellyCam server running elsewhere
                    </Typography>
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button onClick={handleConnect} variant="contained">Connect</Button>
            </DialogActions>
        </Dialog>
    );
};

export const ServerSettingsPanel: React.FC = () => {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();

    // Connection state
    const connectionMode = useAppSelector(selectConnectionMode);
    const connectionStatus = useAppSelector(selectConnectionStatus);
    const connectionError = useAppSelector(selectConnectionError);
    const hasManagedServer = useAppSelector(selectHasManagedServer);
    const managedProcess = useAppSelector(selectManagedProcess);
    const isConnected = useAppSelector(selectIsServerConnected);
    const isTransitioning = useAppSelector(selectIsServerTransitioning);
    const canConnect = useAppSelector(selectCanConnect);
    const canDisconnect = useAppSelector(selectCanDisconnect);

    // Config
    const serverConfig = useAppSelector(selectServerConfig);
    const autoConnect = useAppSelector(selectAutoConnect);
    const autoSpawn = useAppSelector(selectAutoSpawn);
    const preferredPath = useAppSelector(selectPreferredExecutablePath);

    // URLs
    const httpUrl = useAppSelector(selectHttpUrl);
    const wsUrl = useAppSelector(selectWebSocketUrl);

    // WebSocket
    const isWsConnected = useAppSelector(selectIsWebSocketConnected);
    const wsStatus = useAppSelector(selectWebSocketStatus);

    // Executables
    const executables = useAppSelector(selectExecutableCandidates);
    const isRefreshing = useAppSelector(selectIsRefreshingExecutables);

    // Local state
    const [expanded, setExpanded] = useState(false);
    const [connectionDialogOpen, setConnectionDialogOpen] = useState(false);
    const [selectedPath, setSelectedPath] = useState<string | null>(preferredPath);

    // Load executables on mount (Electron only)
    useEffect(() => {
        if (isElectron && executables.length === 0) {
            dispatch(refreshExecutableCandidates());
        }
    }, [isElectron, dispatch, executables.length]);

    // Sync selected path with preferred path from store
    useEffect(() => {
        setSelectedPath(preferredPath);
    }, [preferredPath]);

    const handleStartManaged = async () => {
        try {
            await dispatch(connectToServer({
                mode: 'managed',
                executablePath: selectedPath
            })).unwrap();
        } catch (error) {
            console.error('Failed to start managed server:', error);
        }
    };

    const handleDisconnect = async () => {
        try {
            await dispatch(disconnectFromServer()).unwrap();
        } catch (error) {
            console.error('Failed to disconnect:', error);
        }
    };


    const handleExecutableChange = (event: SelectChangeEvent) => {
        const path = event.target.value;
        setSelectedPath(path);
        dispatch(updateServerConfig({ preferredExecutablePath: path }));
    };

    // Compact collapsed view
    if (!expanded) {
        return (
            <Box sx={{ px: 1, py: 0.5 }}>
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        '&:hover': { opacity: 0.8 }
                    }}
                    onClick={() => setExpanded(true)}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <SettingsIcon sx={{ fontSize: 16 }} />
                        <StatusDot status={connectionStatus} />
                        <Typography variant="caption" sx={{ fontSize: 11 }}>
                            {connectionStatus === 'connected' ? 'Server' : 'Server (Off)'}
                        </Typography>
                    </Box>
                    <IconButton size="small" sx={{ padding: '2px' }}>
                        <ExpandMoreIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                </Box>
                {isTransitioning && (
                    <LinearProgress sx={{ height: 2, mt: 0.5 }} />
                )}
            </Box>
        );
    }

    // Expanded view
    return (
        <>
            <Paper elevation={1} sx={{ mx: 1, my: 0.5, p: 1 }}>
                <Stack spacing={1.5}>
                    {/* Header */}
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                        <Box display="flex" alignItems="center" gap={0.5}>
                            <SettingsIcon sx={{ fontSize: 18 }} color="primary" />
                            <Typography variant="body2" fontWeight={500}>
                                Server
                            </Typography>
                        </Box>
                        <IconButton
                            onClick={() => setExpanded(false)}
                            size="small"
                            sx={{ padding: '2px' }}
                        >
                            <ExpandMoreIcon sx={{ fontSize: 18, transform: 'rotate(180deg)' }} />
                        </IconButton>
                    </Box>

                    {/* Compact Status Section */}
                    <Box sx={{ px: 0.5 }}>
                        {/* Server Status Row */}
                        <Box display="flex" alignItems="center" justifyContent="space-between" mb={0.5}>
                            <Box display="flex" alignItems="center" gap={0.5}>
                                <StatusDot status={connectionStatus} />
                                <Typography variant="caption">
                                    {connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
                                </Typography>
                            </Box>
                            {canConnect && (
                                <Stack direction="row" spacing={0.5}>
                                    {isElectron && (
                                        <Button
                                            variant="contained"
                                            color="primary"
                                            startIcon={<PlayArrowIcon sx={{ fontSize: 14 }} />}
                                            onClick={handleStartManaged}
                                            disabled={isTransitioning}
                                            sx={{ fontSize: 11, py: 0.25, px: 1 }}
                                            size="small"
                                        >
                                            Spawn
                                        </Button>
                                    )}
                                    <Button
                                        variant="outlined"
                                        startIcon={<StorageIcon sx={{ fontSize: 14 }} />}
                                        onClick={() => setConnectionDialogOpen(true)}
                                        disabled={isTransitioning}
                                        sx={{ fontSize: 11, py: 0.25, px: 1 }}
                                        size="small"
                                    >
                                        Connect
                                    </Button>
                                </Stack>
                            )}
                            {canDisconnect && (
                                <Button
                                    variant="contained"
                                    color="error"
                                    startIcon={<StopIcon sx={{ fontSize: 14 }} />}
                                    onClick={handleDisconnect}
                                    disabled={isTransitioning}
                                    sx={{ fontSize: 11, py: 0.25, px: 1 }}
                                    size="small"
                                >
                                    {hasManagedServer ? 'Stop' : 'Disconnect'}
                                </Button>
                            )}
                        </Box>

                        {/* WebSocket Status Row */}
                        <Box display="flex" alignItems="center" justifyContent="space-between">
                            <Box display="flex" alignItems="center" gap={0.5}>
                                <StatusDot status={isWsConnected ? 'connected' : wsStatus} />
                                <Typography variant="caption">
                                    WebSocket
                                </Typography>
                            </Box>
                            {isConnected && (
                                <Button
                                    variant="text"
                                    color={isWsConnected ? "error" : "primary"}
                                    onClick={() => isWsConnected ? handleWebSocketDisconnect() : handleWebSocketConnect()}
                                    sx={{ fontSize: 11, py: 0, px: 0.5, minWidth: 'auto' }}
                                    size="small"
                                >
                                    {isWsConnected ? 'Disconnect' : 'Connect'}
                                </Button>
                            )}
                        </Box>

                        {isTransitioning && <LinearProgress sx={{ height: 2, mt: 0.5 }} />}
                    </Box>

                    {connectionError && (
                        <Alert severity="error" sx={{ py: 0.25, px: 1, fontSize: 11 }}>
                            {connectionError}
                        </Alert>
                    )}

                    {/* Configuration Options */}
                    <Stack spacing={1} sx={{ px: 0.5 }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={autoConnect}
                                    onChange={(e) => dispatch(updateServerConfig({ autoConnect: e.target.checked }))}
                                    size="small"
                                />
                            }
                            label={
                                <Typography variant="caption">Auto-connect WS</Typography>
                            }
                            sx={{ m: 0 }}
                        />

                        {isElectron && (
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={autoSpawn}
                                        onChange={(e) => dispatch(updateServerConfig({ autoSpawn: e.target.checked }))}
                                        size="small"
                                    />
                                }
                                label={
                                    <Typography variant="caption">Auto-spawn</Typography>
                                }
                                sx={{ m: 0 }}
                            />
                        )}
                    </Stack>
                </Stack>
            </Paper>

            <ConnectionDialog
                open={connectionDialogOpen}
                onClose={() => setConnectionDialogOpen(false)}
            />
        </>
    );
};
