import * as React from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    Collapse,
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
    Typography,
} from '@mui/material';
import {
    CheckCircle as CheckCircleIcon,
    Error as ErrorIcon,
    ExpandMore as ExpandMoreIcon,
    FolderOpen as FolderOpenIcon,
    Info as InfoIcon,
    Link as LinkIcon,
    LinkOff as LinkOffIcon,
    PlayArrow as PlayArrowIcon,
    Refresh as RefreshIcon,
    Settings as SettingsIcon,
    Stop as StopIcon,
    Warning as WarningIcon,
} from '@mui/icons-material';
import {styled} from '@mui/material/styles';
import {
    selectBaseHttpUrl,
    selectIsServerAlive,
    selectIsServerTransitioning,
    selectIsWebSocketConnected,
    selectServerConfig,
    selectServerError,
    selectServerProcessInfo,
    selectServerStatus,
    selectServerUrls, selectWebSocketUrl,
    ServerStatus,
    startServer,
    stopServer,
    updateServerConfig,
    useAppDispatch,
    useAppSelector,
} from "@/store";
import {websocketService} from "@/services/websocket/websocket-service";
import {useElectronIPC} from "@/services/electron-ipc/electron-ipc";

const ExpandMoreStyled = styled((props: any) => {
    const {expand, ...other} = props;
    return <IconButton {...other} />;
})(({theme, expand}) => ({
    transform: !expand ? 'rotate(0deg)' : 'rotate(180deg)',
    marginLeft: 'auto',
    transition: theme.transitions.create('transform', {
        duration: theme.transitions.duration.shortest,
    }),
}));

const StatusChip = styled(Chip)<{ status: ServerStatus }>(({theme, status}) => {
    const getStatusColor = () => {
        switch (status) {
            case 'alive':
                return {bg: theme.palette.success.main, text: theme.palette.success.contrastText};
            case 'spawning':
                return {bg: theme.palette.warning.main, text: theme.palette.warning.contrastText};
            case 'shutting-down':
                return {bg: theme.palette.info.main, text: theme.palette.info.contrastText};
            case 'error':
                return {bg: theme.palette.error.main, text: theme.palette.error.contrastText};
            default:
                return {bg: theme.palette.grey[500], text: theme.palette.common.white};
        }
    };

    const colors = getStatusColor();
    return {
        backgroundColor: colors.bg,
        color: colors.text,
        fontWeight: 600,
    };
});

export const ServerSettingsPanel: React.FC = () => {
    const {api, isElectron} = useElectronIPC();
    // Redux hooks
    const dispatch = useAppDispatch();

    // Server selectors
    const serverStatus = useAppSelector(selectServerStatus);
    const serverConfig = useAppSelector(selectServerConfig);
    const serverError = useAppSelector(selectServerError);
    const baseHttpUrl = useAppSelector(selectBaseHttpUrl);
    const webSocketUrl = useAppSelector(selectWebSocketUrl);
    const processInfo = useAppSelector(selectServerProcessInfo);
    const isServerAlive = useAppSelector(selectIsServerAlive);
    const isServerTransitioning = useAppSelector(selectIsServerTransitioning);
    const serverUrls = useAppSelector(selectServerUrls);

    // WebSocket selectors
    const isWebSocketConnected = useAppSelector(selectIsWebSocketConnected);

    const [expanded, setExpanded] = React.useState(false);
    const [candidates, setCandidates] = React.useState<any[]>([]);
    const [selectedPath, setSelectedPath] = React.useState<string | null>(null);
    const [isRefreshing, setIsRefreshing] = React.useState(false);

    React.useEffect(() => {
        if (api && isElectron) {
            loadExecutableCandidates().then(r => {
            }).catch(
                error => console.error('Error loading executable candidates:', error)
            )
        }
    }, [api, isElectron]);

    React.useEffect(() => {
        // Auto-connect behavior
        if (serverConfig.autoConnect && serverStatus === 'alive' && !isWebSocketConnected) {
            websocketService.connect();
        }
    }, [serverConfig.autoConnect, serverStatus, isWebSocketConnected]);

    const loadExecutableCandidates = async () => {
        if (!api) return;
        setIsRefreshing(true);
        try {
            const [path, candidateList] = await Promise.all([
                api.pythonServer.getExecutablePath.query(),
                api.pythonServer.getExecutableCandidates.query(),
            ]);
            setSelectedPath(path);
            setCandidates(candidateList);
        } catch (error) {
            console.error('Failed to load executables:', error);
        } finally {
            setIsRefreshing(false);
        }
    };

    const handleServerToggle = async () => {
        if (serverStatus === 'alive' || serverStatus === 'spawning') {
            // Stop the server using the thunk
            dispatch(stopServer());
        } else {
            // Start the server using the thunk
            dispatch(startServer({exePath: selectedPath}));
        }
    };

    const handleWebSocketToggle = () => {
        if (isWebSocketConnected) {
            websocketService.disconnect();
        } else {
            websocketService.connect();
        }
    };

    const handleSelectCustomExecutable = async () => {
        if (!api) return;
        const path = await api.fileSystem.selectExecutableFile.mutate();
        if (path) {
            setSelectedPath(path);
            // Start server with the new path using the thunk
            dispatch(startServer({exePath: path}));
        }
    };

    const handleExecutableChange = (event: SelectChangeEvent) => {
        setSelectedPath(event.target.value);
    };

    const updateConfig = (updates: Partial<typeof serverConfig>) => {
        dispatch(updateServerConfig(updates));
    };

    const getStatusIcon = (status: ServerStatus) => {
        switch (status) {
            case 'alive':
                return <CheckCircleIcon color="success"/>;
            case 'spawning':
                return <WarningIcon color="warning"/>;
            case 'error':
                return <ErrorIcon color="error"/>;
            default:
                return <InfoIcon color="disabled"/>;
        }
    };

    const isServerOperational = serverStatus === 'alive';

    return (
        <Card elevation={2} sx={{m: 2}}>
            <CardContent>
                <Stack spacing={3}>
                    {/* Header */}
                    <Box display="flex" alignItems="center" justifyContent="space-between">
                        <Box display="flex" alignItems="center" gap={1}>
                            <SettingsIcon color="primary"/>
                            <Typography variant="h6" component="h2">
                                Server Management
                            </Typography>
                        </Box>
                        <ExpandMoreStyled
                            expand={expanded}
                            onClick={() => setExpanded(!expanded)}
                            aria-expanded={expanded}
                            aria-label="show more"
                        >
                            <ExpandMoreIcon/>
                        </ExpandMoreStyled>
                    </Box>

                    {/* Status Section */}
                    <Paper elevation={0} sx={{p: 2, bgcolor: 'background.default'}}>
                        <Stack spacing={2}>
                            <Box display="flex" alignItems="center" justifyContent="space-between">
                                <Box display="flex" alignItems="center" gap={2}>
                                    {getStatusIcon(serverStatus)}
                                    <Typography variant="body1" fontWeight={500}>
                                        Python Server
                                    </Typography>
                                    <StatusChip
                                        label={serverStatus.toUpperCase()}
                                        status={serverStatus}
                                        size="small"
                                    />
                                </Box>
                                <Button
                                    variant="contained"
                                    color={isServerOperational ? "error" : "primary"}
                                    startIcon={isServerOperational ? <StopIcon/> : <PlayArrowIcon/>}
                                    onClick={handleServerToggle}
                                    disabled={isServerTransitioning}
                                    size="small"
                                >
                                    {isServerOperational ? 'Stop' : 'Start'}
                                </Button>
                            </Box>

                            {isServerTransitioning && <LinearProgress/>}

                            <Box display="flex" alignItems="center" justifyContent="space-between">
                                <Box display="flex" alignItems="center" gap={2}>
                                    {isWebSocketConnected ? <LinkIcon color="success"/> :
                                        <LinkOffIcon color="disabled"/>}
                                    <Typography variant="body1" fontWeight={500}>
                                        WebSocket
                                    </Typography>
                                    <Chip
                                        label={isWebSocketConnected ? 'CONNECTED' : 'DISCONNECTED'}
                                        color={isWebSocketConnected ? 'success' : 'default'}
                                        size="small"
                                    />
                                </Box>
                                <Button
                                    variant="outlined"
                                    color={isWebSocketConnected ? "error" : "primary"}
                                    startIcon={isWebSocketConnected ? <LinkOffIcon/> : <LinkIcon/>}
                                    onClick={handleWebSocketToggle}
                                    disabled={!isServerOperational}
                                    size="small"
                                >
                                    {isWebSocketConnected ? 'Disconnect' : 'Connect'}
                                </Button>
                            </Box>
                        </Stack>
                    </Paper>

                    {serverError && (
                        <Alert severity="error" onClose={() => {
                        }}>
                            {serverError}
                        </Alert>
                    )}

                    {/* Configuration Section */}
                    <Collapse in={expanded} timeout="auto" unmountOnExit>
                        <Stack spacing={3}>
                            <Divider/>

                            {/* Auto-connect Setting */}
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={serverConfig.autoConnect}
                                        onChange={(e) => updateConfig({autoConnect: e.target.checked})}
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

                            {/* URL Configuration */}
                            <Stack direction="row" spacing={2}>
                                <TextField
                                    label="Host"
                                    value={serverConfig.host}
                                    onChange={(e) => updateConfig({host: e.target.value})}
                                    size="small"
                                    fullWidth
                                />
                                <TextField
                                    label="Port"
                                    type="number"
                                    value={serverConfig.port}
                                    onChange={(e) => updateConfig({port: parseInt(e.target.value) || 8006})}
                                    size="small"
                                    sx={{width: 120}}
                                />
                            </Stack>

                            {/* URLs Display */}
                            <Paper elevation={0} sx={{p: 2, bgcolor: 'background.default'}}>
                                <Stack spacing={1}>
                                    <Typography variant="caption" color="text.secondary">
                                        API URL
                                    </Typography>
                                    <Typography variant="body2" fontFamily="monospace" sx={{wordBreak: 'break-all'}}>
                                        {baseHttpUrl}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary" sx={{mt: 1}}>
                                        WebSocket URL
                                    </Typography>
                                    <Typography variant="body2" fontFamily="monospace" sx={{wordBreak: 'break-all'}}>
                                        {webSocketUrl}
                                    </Typography>
                                </Stack>
                            </Paper>

                            {/* Executable Selection */}
                            {isElectron && (
                                <>
                                    <Divider/>
                                    <Box>
                                        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                                            <Typography variant="subtitle2">
                                                Python Executable
                                            </Typography>
                                            <IconButton
                                                onClick={loadExecutableCandidates}
                                                disabled={isRefreshing}
                                                size="small"
                                            >
                                                <RefreshIcon/>
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
                                                    {candidates.map((candidate) => (
                                                        <MenuItem
                                                            key={candidate.path}
                                                            value={candidate.path}
                                                            disabled={!candidate.isValid}
                                                        >
                                                            <Box>
                                                                <Typography variant="body2">
                                                                    {candidate.name}
                                                                </Typography>
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
                                                startIcon={<FolderOpenIcon/>}
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
    );
};
