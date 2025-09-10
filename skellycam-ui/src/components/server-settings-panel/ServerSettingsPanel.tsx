// components/ServerSettingsPanel.tsx
import React, { useEffect, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    LinearProgress,
    MenuItem,
    Paper,
    Select,
    SelectChangeEvent,
    Stack,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import {
    CheckCircle as CheckCircleIcon,
    Computer as ComputerIcon,
    Error as ErrorIcon,
    ExpandMore as ExpandMoreIcon,
    FolderOpen as FolderOpenIcon,
    Link as LinkIcon,
    LinkOff as LinkOffIcon,
    PlayArrow as PlayArrowIcon,
    Refresh as RefreshIcon,
    Settings as SettingsIcon,
    Stop as StopIcon,
    Storage as StorageIcon,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
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
import { websocketService } from "@/services/websocket/websocket-service";
import { useElectronIPC } from "@/services/electron-ipc/electron-ipc";

const ExpandMoreStyled = styled(IconButton)(({ theme }) => ({
    marginLeft: 'auto',
    transition: theme.transitions.create('transform', {
        duration: theme.transitions.duration.shortest,
    }),
}));

const StatusChip = styled(Chip)<{ status: string }>(({ theme, status }) => {
    const getStatusColor = () => {
        switch (status) {
            case 'connected':
                return { bg: theme.palette.success.main, text: theme.palette.success.contrastText };
            case 'connecting':
            case 'disconnecting':
                return { bg: theme.palette.warning.main, text: theme.palette.warning.contrastText };
            case 'error':
                return { bg: theme.palette.error.main, text: theme.palette.error.contrastText };
            default:
                return { bg: theme.palette.grey[500], text: theme.palette.common.white };
        }
    };

    const colors = getStatusColor();
    return {
        backgroundColor: colors.bg,
        color: colors.text,
        fontWeight: 600,
    };
});

// External server connection dialog
const ConnectionDialog: React.FC<{
    open: boolean;
    onClose: () => void;
}> = ({ open, onClose }) => {
    const dispatch = useAppDispatch();
    const config = useAppSelector(selectServerConfig);
    const [host, setHost] = useState(config.host);
    const [port, setPort] = useState(config.port);

    const handleConnect = async () => {
        // Update config first
        dispatch(updateServerConfig({ host, port }));

        // Connect to external server
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
                    />
                    <TextField
                        label="Port"
                        type="number"
                        value={port}
                        onChange={(e) => setPort(parseInt(e.target.value) || 8006)}
                        fullWidth
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

    const handleWebSocketConnect = () => {
        dispatch(websocketStatusChanged('connecting'));
        websocketService.connect();
    };

    const handleWebSocketDisconnect = () => {
        websocketService.disconnect();
    };

    const handleWebSocketToggle = () => {
        if (isWsConnected) {
            handleWebSocketDisconnect();
        } else {
            handleWebSocketConnect();
        }
    };

    const handleSelectCustomExecutable = async () => {
        if (!api) return;
        const path = await api.fileSystem.selectExecutableFile.mutate();
        if (path) {
            setSelectedPath(path);
            dispatch(updateServerConfig({ preferredExecutablePath: path }));
        }
    };

    const handleExecutableChange = (event: SelectChangeEvent) => {
        const path = event.target.value;
        setSelectedPath(path);
        dispatch(updateServerConfig({ preferredExecutablePath: path }));
    };

    const getStatusIcon = () => {
        switch (connectionStatus) {
            case 'connected':
                return <CheckCircleIcon color="success" />;
            case 'connecting':
            case 'disconnecting':
                return <CircularProgress size={20} />;
            case 'error':
                return <ErrorIcon color="error" />;
            default:
                return <InfoIcon color="disabled" />;
        }
    };

    const getConnectionDescription = () => {
        if (connectionStatus === 'disconnected') return 'Not connected';
        if (connectionStatus === 'connecting') {
            return connectionMode === 'managed' ? 'Starting server...' : 'Connecting...';
        }
        if (connectionStatus === 'disconnecting') return 'Disconnecting...';
        if (connectionStatus === 'error') return 'Connection error';
        if (connectionStatus === 'connected') {
            if (connectionMode === 'managed') return 'Connected (managed)';
            if (connectionMode === 'external') return 'Connected (external)';
            return 'Connected';
        }
        return connectionStatus;
    };

    return (
        <>
            <Card elevation={2} sx={{ m: 2 }}>
                <CardContent>
                    <Stack spacing={3}>
                        {/* Header */}
                        <Box display="flex" alignItems="center" justifyContent="space-between">
                            <Box display="flex" alignItems="center" gap={1}>
                                <SettingsIcon color="primary" />
                                <Typography variant="h6" component="h2">
                                    Server Management
                                </Typography>
                            </Box>
                            <ExpandMoreStyled
                                onClick={() => setExpanded(!expanded)}
                                sx={{
                                    transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                }}
                            >
                                <ExpandMoreIcon />
                            </ExpandMoreStyled>
                        </Box>

                        {/* Status Section */}
                        <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                            <Stack spacing={2}>
                                {/* Server Status */}
                                <Box display="flex" alignItems="center" justifyContent="space-between">
                                    <Box display="flex" alignItems="center" gap={2}>
                                        {getStatusIcon()}
                                        <Typography variant="body1" fontWeight={500}>
                                            Python Server
                                        </Typography>
                                        <StatusChip
                                            label={getConnectionDescription()}
                                            status={connectionStatus}
                                            size="small"
                                        />
                                        {hasManagedServer && (
                                            <Tooltip title="Server spawned by this app">
                                                <ComputerIcon fontSize="small" color="primary" />
                                            </Tooltip>
                                        )}
                                    </Box>
                                    <Box>
                                        {canConnect && (
                                            <Stack direction="row" spacing={1}>
                                                {isElectron && (
                                                    <Button
                                                        variant="contained"
                                                        color="primary"
                                                        startIcon={<PlayArrowIcon />}
                                                        onClick={handleStartManaged}
                                                        disabled={isTransitioning}
                                                        size="small"
                                                    >
                                                        Spawn
                                                    </Button>
                                                )}
                                                <Button
                                                    variant="outlined"
                                                    startIcon={<StorageIcon />}
                                                    onClick={() => setConnectionDialogOpen(true)}
                                                    disabled={isTransitioning}
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
                                                startIcon={<StopIcon />}
                                                onClick={handleDisconnect}
                                                disabled={isTransitioning}
                                                size="small"
                                            >
                                                {hasManagedServer ? 'Stop' : 'Disconnect'}
                                            </Button>
                                        )}
                                    </Box>
                                </Box>

                                {isTransitioning && <LinearProgress />}

                                {/* WebSocket Status */}
                                <Box display="flex" alignItems="center" justifyContent="space-between">
                                    <Box display="flex" alignItems="center" gap={2}>
                                        {isWsConnected ? <LinkIcon color="success" /> : <LinkOffIcon color="disabled" />}
                                        <Typography variant="body1" fontWeight={500}>
                                            WebSocket
                                        </Typography>
                                        <StatusChip
                                            label={wsStatus.toUpperCase()}
                                            status={isWsConnected ? 'connected' : wsStatus}
                                            size="small"
                                        />
                                    </Box>
                                    <Button
                                        variant="outlined"
                                        color={isWsConnected ? "error" : "primary"}
                                        startIcon={isWsConnected ? <LinkOffIcon /> : <LinkIcon />}
                                        onClick={handleWebSocketToggle}
                                        disabled={!isConnected && connectionMode === 'managed'}
                                        size="small"
                                    >
                                        {isWsConnected ? 'Disconnect' : 'Connect'}
                                    </Button>
                                </Box>
                            </Stack>
                        </Paper>

                        {connectionError && (
                            <Alert severity="error">{connectionError}</Alert>
                        )}

                        {/* Expanded Configuration */}
                        <Collapse in={expanded} timeout="auto" unmountOnExit>
                            <Stack spacing={3}>
                                <Divider />

                                {/* Settings */}
                                <FormControlLabel
                                    control={
                                        <Switch
                                            checked={autoConnect}
                                            onChange={(e) => dispatch(updateServerConfig({ autoConnect: e.target.checked }))}
                                            color="primary"
                                        />
                                    }
                                    label={
                                        <Box>
                                            <Typography variant="body1">Auto-connect WebSocket</Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                Automatically connect WebSocket when server starts
                                            </Typography>
                                        </Box>
                                    }
                                />

                                {isElectron && (
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={autoSpawn}
                                                onChange={(e) => dispatch(updateServerConfig({ autoSpawn: e.target.checked }))}
                                                color="primary"
                                            />
                                        }
                                        label={
                                            <Box>
                                                <Typography variant="body1">Auto-spawn server</Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    Automatically spawn server on app start
                                                </Typography>
                                            </Box>
                                        }
                                    />
                                )}

                                {/* URL Configuration */}
                                <Stack direction="row" spacing={2}>
                                    <TextField
                                        label="Host"
                                        value={serverConfig.host}
                                        onChange={(e) => dispatch(updateServerConfig({ host: e.target.value }))}
                                        size="small"
                                        fullWidth
                                    />
                                    <TextField
                                        label="Port"
                                        type="number"
                                        value={serverConfig.port}
                                        onChange={(e) => dispatch(updateServerConfig({ port: parseInt(e.target.value) || 8006 }))}
                                        size="small"
                                        sx={{ width: 120 }}
                                    />
                                </Stack>

                                {/* URLs Display */}
                                <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                                    <Stack spacing={1}>
                                        <Typography variant="caption" color="text.secondary">API URL</Typography>
                                        <Typography variant="body2" fontFamily="monospace">{httpUrl}</Typography>
                                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>WebSocket URL</Typography>
                                        <Typography variant="body2" fontFamily="monospace">{wsUrl}</Typography>
                                    </Stack>
                                </Paper>

                                {/* Process Info */}
                                {managedProcess && (
                                    <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                                        <Typography variant="caption" color="text.secondary">Process Info</Typography>
                                        <Typography variant="body2">PID: {managedProcess.pid || 'Unknown'}</Typography>
                                        <Typography variant="caption">{managedProcess.executablePath}</Typography>
                                    </Paper>
                                )}

                                {/* Executable Selection (Electron only) */}
                                {isElectron && (
                                    <>
                                        <Divider />
                                        <Box>
                                            <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                                                <Typography variant="subtitle2">Python Executable</Typography>
                                                <IconButton
                                                    onClick={() => dispatch(refreshExecutableCandidates())}
                                                    disabled={isRefreshing}
                                                    size="small"
                                                >
                                                    <RefreshIcon />
                                                </IconButton>
                                            </Box>

                                            <Stack spacing={2}>
                                                <FormControl fullWidth size="small">
                                                    <InputLabel>Select Executable</InputLabel>
                                                    <Select
                                                        value={selectedPath || ''}
                                                        onChange={handleExecutableChange}
                                                        label="Select Executable"
                                                    >
                                                        {executables.map((candidate) => (
                                                            <MenuItem
                                                                key={candidate.path}
                                                                value={candidate.path}
                                                                disabled={!candidate.isValid}
                                                            >
                                                                <Box>
                                                                    <Typography variant="body2">{candidate.name}</Typography>
                                                                    <Typography variant="caption" color="text.secondary">
                                                                        {candidate.description}
                                                                        {!candidate.isValid && ` - ${candidate.error}`}
                                                                    </Typography>
                                                                </Box>
                                                            </MenuItem>
                                                        ))}
                                                    </Select>
                                                </FormControl>

                                                <Button
                                                    variant="outlined"
                                                    startIcon={<FolderOpenIcon />}
                                                    onClick={handleSelectCustomExecutable}
                                                    fullWidth
                                                >
                                                    Browse for Executable
                                                </Button>
                                            </Stack>
                                        </Box>
                                    </>
                                )}
                            </Stack>
                        </Collapse>
                    </Stack>
                </CardContent>
            </Card>

            <ConnectionDialog
                open={connectionDialogOpen}
                onClose={() => setConnectionDialogOpen(false)}
            />
        </>
    );
};
