import * as React from 'react';
import Box from '@mui/material/Box';
import {SimpleTreeView} from '@mui/x-tree-view/SimpleTreeView';
import {TreeItem} from '@mui/x-tree-view/TreeItem';
import {
    Alert,
    Checkbox,
    Chip,
    FormControl,
    FormControlLabel,
    IconButton,
    InputAdornment,
    InputLabel,
    MenuItem,
    Select,
    Slider,
    Stack,
    TextField,
    Typography
} from '@mui/material';
import WebsocketConnectionStatus from './WebsocketConnectionStatus';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import RefreshIcon from '@mui/icons-material/Refresh';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {ServerConnectionStatus} from "@/components/server-settings-panel/ServerConnectionStatus";
import {usePythonServerContext} from "@/context/python-server-context/PythonServerContext";

interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
}

export const ServerSettingsPanel = () => {
    const {isConnected} = useWebSocketContext();
    const {serverStatus, startPythonServer} = usePythonServerContext();

    // State for executable path management
    const [executableCandidates, setExecutableCandidates] = React.useState<ExecutableCandidate[]>([]);
    const [selectedExecutablePath, setSelectedExecutablePath] = React.useState<string>('');
    const [customExecutablePath, setCustomExecutablePath] = React.useState<string>('');
    const [currentExecutablePath, setCurrentExecutablePath] = React.useState<string | null>(null);
    const [isLoading, setIsLoading] = React.useState(false);

    // Other settings state
    const [host, setHost] = React.useState('localhost');
    const [httpPort, setHttpPort] = React.useState(8006);
    const [limitFramerate, setLimitFramerate] = React.useState(false);
    const [framerate, setFramerate] = React.useState(30);
    const [preShrink, setPreShrink] = React.useState(true);
    const [shrinkFactor, setShrinkFactor] = React.useState(0.5);

    const maxFramerate = 60;

    // Load executable candidates and current path on component mount
    React.useEffect(() => {
        loadExecutableInfo();
    }, []);

    const loadExecutableInfo = async () => {
        setIsLoading(true);
        try {
            // Get current executable path
            const currentPath = await window.electronAPI.getPythonServerExecutablePath();
            setCurrentExecutablePath(currentPath);

            // Get all candidates with validation status
            const candidates = await window.electronAPI.getPythonServerExecutableCandidates();
            setExecutableCandidates(candidates);

            // Set the first valid candidate as selected, or current path if available
            const validCandidate = candidates.find(c => c.isValid);
            if (currentPath) {
                setSelectedExecutablePath(currentPath);
            } else if (validCandidate) {
                setSelectedExecutablePath(validCandidate.path);
            }
        } catch (error) {
            console.error('Error loading executable info:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleRefreshCandidates = async () => {
        setIsLoading(true);
        try {
            const candidates = await window.electronAPI.refreshPythonServerCandidates();
            setExecutableCandidates(candidates);
        } catch (error) {
            console.error('Error refreshing candidates:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSelectCustomExecutable = async () => {
        try {
            const selectedPath = await window.electronAPI.selectExecutableFile();
            if (selectedPath) {
                setCustomExecutablePath(selectedPath);
                setSelectedExecutablePath(selectedPath);
            }
        } catch (error) {
            console.error('Error selecting executable:', error);
        }
    };

    const handleFramerateChange = (event: Event, newValue: number | number[]) => {
        setFramerate(newValue as number);
    };

    const handleShrinkFactorChange = (event: Event, newValue: number | number[]) => {
        setShrinkFactor(newValue as number);
    };

    const handleSpawnServer = () => {
        const executablePath = selectedExecutablePath || null;
        startPythonServer(executablePath);
    };

    const getExecutableOptions = () => {
        const options = executableCandidates.map(candidate => ({
            value: candidate.path,
            label: `${candidate.name} - ${candidate.description}`,
            isValid: candidate.isValid,
            error: candidate.error
        }));

        // Add custom path if it exists and isn't already in candidates
        if (customExecutablePath && !options.some(opt => opt.value === customExecutablePath)) {
            options.push({
                value: customExecutablePath,
                label: `Custom: ${customExecutablePath}`,
                isValid: undefined, // Unknown validation status
                error: undefined
            });
        }

        return options;
    };

    return (
        <Box sx={{padding: 2, color: 'text.primary'}}>
            <SimpleTreeView
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon
                }}
                sx={{flexGrow: 1, maxWidth: 600}}
            >
                <TreeItem
                    itemId="server-status"
                    label={
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                            <Box
                                sx={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    bgcolor: serverStatus == 'alive' ? 'rgba(0, 255, 255, 0.25)' : 'rgba(255, 0, 0, 0.25)',
                                    px: 1,
                                    py: 0.5,
                                    borderRadius: 1
                                }}
                            >
                                server: {serverStatus}
                            </Box>
                            <Box
                                sx={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    bgcolor: isConnected ? 'rgba(0, 255, 255, 0.25)' : 'rgba(255, 0, 0, 0.25)',
                                    px: 1,
                                    py: 0.5,
                                    borderRadius: 1
                                }}
                            >
                                ws: {isConnected ? 'Connected' : 'Disconnected'}
                            </Box>
                        </Box>
                    }
                >
                    <Box sx={{pl: 2, pt: 1, borderTop: '2px solid', borderColor: 'darkcyan'}}>
                        <ServerConnectionStatus/>
                        <WebsocketConnectionStatus/>

                        <TreeItem itemId="server-settings" label="Server Settings">
                            <TreeItem itemId="python-server-executable" label="Python server executable">
                                <Box sx={{pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2}}>


                                    {/* Current executable path display */}
                                    {currentExecutablePath && (
                                        <Typography variant="body2">
                                            <strong>Current executable:</strong><br/>
                                            {currentExecutablePath}
                                        </Typography>
                                    )}

                                    {/*Executable path selector */}
                                    <Stack spacing={2}>
                                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                                            <FormControl fullWidth size="small">
                                                <InputLabel id="executable-select-label">
                                                    Server executable
                                                </InputLabel>
                                                <Select
                                                    labelId="executable-select-label"
                                                    value={selectedExecutablePath}
                                                    onChange={(e) => setSelectedExecutablePath(e.target.value)}
                                                    label="Server executable"
                                                    disabled={isLoading}
                                                >
                                                    {getExecutableOptions().map((option) => (
                                                        <MenuItem
                                                            key={option.value}
                                                            value={option.value}
                                                            disabled={option.isValid === false}
                                                        >
                                                            <Box sx={{
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                gap: 1,
                                                                width: '100%'
                                                            }}>
                                                                <Typography variant="body2" sx={{flexGrow: 1}}>
                                                                    {option.label}
                                                                </Typography>
                                                                {option.isValid === true && (
                                                                    <Chip label="Valid" color="success" size="small"/>
                                                                )}
                                                                {option.isValid === false && (
                                                                    <Chip label="Invalid" color="error" size="small"/>
                                                                )}
                                                            </Box>
                                                        </MenuItem>
                                                    ))}
                                                </Select>
                                            </FormControl>
                                            <IconButton
                                                onClick={handleRefreshCandidates}
                                                disabled={isLoading}
                                                title="Refresh executable candidates"
                                            >
                                                <RefreshIcon/>
                                            </IconButton>
                                        </Box>

                                        {/* Custom path input */}
                                        <TextField
                                            label="Custom executable path"
                                            value={customExecutablePath}
                                            onChange={(e) => {
                                                setCustomExecutablePath(e.target.value);
                                                setSelectedExecutablePath(e.target.value);
                                            }}
                                            size="small"
                                            placeholder="Enter path or browse..."
                                            InputProps={{
                                                endAdornment: (
                                                    <InputAdornment position="end">
                                                        <IconButton
                                                            onClick={handleSelectCustomExecutable}
                                                            size="small"
                                                            title="Browse for executable"
                                                        >
                                                            <FolderOpenIcon/>
                                                        </IconButton>
                                                    </InputAdornment>
                                                ),
                                            }}
                                        />

                                        {/* Show validation errors for selected path */}
                                        {selectedExecutablePath && (
                                            (() => {
                                                const selectedCandidate = executableCandidates.find(c => c.path === selectedExecutablePath);
                                                if (selectedCandidate?.isValid === false) {
                                                    return (
                                                        <Alert severity="error">
                                                            <Typography variant="body2">
                                                                <strong>Validation Error:</strong><br/>
                                                                {selectedCandidate.error}
                                                            </Typography>
                                                        </Alert>
                                                    );
                                                }
                                                return null;
                                            })()
                                        )}
                                    </Stack>

                                </Box>
                            </TreeItem>
                            <TreeItem itemId="server-api-urls" label="Server API URL">
                                <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mt:2}}>
                                    <TextField
                                        label="Host"
                                        value={host}
                                        onChange={(e) => setHost(e.target.value)}
                                        size="small"
                                        sx={{flex: 1}}
                                        disabled={true}
                                    />
                                    <TextField
                                        label="HTTP Port"
                                        type="number"
                                        value={httpPort}
                                        onChange={(e) => setHttpPort(Number(e.target.value))}
                                        size="small"
                                        sx={{width: 100}}
                                        disabled={true}
                                    />
                                </Box>

                                <Typography variant="body2" color="textSecondary" sx={{mt:2}}>
                                    WebSocket URL: ws://{host}:{httpPort}/websocket/connect
                                </Typography>
                            </TreeItem>
                        </TreeItem>

                        <TreeItem itemId="display-settings" label="Display Settings">
                            <Box sx={{pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2}}>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={limitFramerate}
                                            onChange={(e) => setLimitFramerate(e.target.checked)}
                                            disabled={true}
                                        />
                                    }
                                    label="Limit display framerate"
                                />

                                {limitFramerate && (
                                    <Box sx={{pl: 4}}>
                                        <Typography gutterBottom>
                                            Framerate: {framerate} FPS
                                        </Typography>
                                        <Slider
                                            value={framerate}
                                            onChange={handleFramerateChange}
                                            min={0}
                                            max={maxFramerate}
                                            valueLabelDisplay="auto"
                                            size="small"
                                            disabled={true}
                                        />
                                    </Box>
                                )}

                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={preShrink}
                                            onChange={(e) => setPreShrink(e.target.checked)}
                                            disabled={true}
                                        />
                                    }
                                    label="Pre-shrink images"
                                />

                                {preShrink && (
                                    <Box sx={{pl: 4}}>
                                        <Typography gutterBottom>
                                            Shrink factor: {shrinkFactor.toFixed(2)}
                                        </Typography>
                                        <Slider
                                            value={shrinkFactor}
                                            onChange={handleShrinkFactorChange}
                                            min={0}
                                            max={1}
                                            step={0.01}
                                            valueLabelDisplay="auto"
                                            size="small"
                                            disabled={true}
                                        />
                                    </Box>
                                )}
                            </Box>
                        </TreeItem>
                    </Box>
                </TreeItem>
            </SimpleTreeView>
        </Box>
    )
        ;
};
