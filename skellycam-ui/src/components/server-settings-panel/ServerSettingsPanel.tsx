import * as React from 'react';
import Box from '@mui/material/Box';
import {SimpleTreeView} from '@mui/x-tree-view/SimpleTreeView';
import {TreeItem} from '@mui/x-tree-view/TreeItem';
import {Checkbox, FormControlLabel, Slider, TextField, Typography} from '@mui/material';
import WebsocketConnectionStatus from './WebsocketConnectionStatus';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {ServerConnectionStatus} from "@/components/server-settings-panel/ServerConnectionStatus";
import {usePythonServerContext} from "@/context/python-server-context/PythonServerContext";
import {ExecutablePathSelector} from './ExecutablePathSelector';
import Link from "@mui/material/Link";


export const ServerSettingsPanel = () => {
    const {isConnected} = useWebSocketContext();
    const {serverStatus, startPythonServer} = usePythonServerContext();

    // State for executable path management
    const [currentExecutablePath, setCurrentExecutablePath] = React.useState<string | null>(null);
    // Other settings state
    const [host, setHost] = React.useState('localhost');
    const [httpPort, setHttpPort] = React.useState(8006);
    const [limitFramerate, setLimitFramerate] = React.useState(false);
    const [framerate, setFramerate] = React.useState(30);
    const [preShrink, setPreShrink] = React.useState(true);
    const [shrinkFactor, setShrinkFactor] = React.useState(0.5);

    const maxFramerate = 60;

    // Load current executable path on component mount
    React.useEffect(() => {
        loadCurrentPath().then(r => {
            console.log('Loaded current executable path:', r);
        });
    }, []);

    const loadCurrentPath = async () => {
        try {
            const currentPath = await window.electronAPI.getPythonServerExecutablePath();
            setCurrentExecutablePath(currentPath);
        } catch (error) {
            console.error('Error loading current path:', error);
        }
    };

    const handlePathSelect = (path: string) => {
        // Start server with selected path
        console.log('Starting Python server with path:', path);
        startPythonServer(path);
        setCurrentExecutablePath(path);
    };

    const handleFramerateChange = (event: Event, newValue: number | number[]) => {
        setFramerate(newValue as number);
    };

    const handleShrinkFactorChange = (event: Event, newValue: number | number[]) => {
        setShrinkFactor(newValue as number);
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
                                    bgcolor: serverStatus === 'alive'
                                        ? 'rgba(0, 255, 255, 0.25)'
                                        : serverStatus === 'spawning'
                                            ? 'rgba(255, 255, 0, 0.25)'

                                            : 'rgba(255, 0, 0, 0.25)',
                                    px: 1,
                                    py: 0.5,
                                    borderRadius: 1
                                }}
                            >
                                {serverStatus}
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
                                {isConnected ? 'connected' : 'not-connected'}
                            </Box>
                        </Box>
                    }
                >
                    <Box sx={{pl: 2, pt: 1, borderTop: '2px solid', borderColor: 'darkcyan'}}>
                        <ServerConnectionStatus/>
                        <WebsocketConnectionStatus/>


                        <Box sx={{pl: 2, pt: 2}}>
                            <ExecutablePathSelector
                                onPathSelect={handlePathSelect}
                                currentPath={currentExecutablePath}
                            />
                        </Box>
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mt: 2}}>
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

                        <Typography variant="body2" color="textSecondary" sx={{mt: 2}}>
                            API DOCS URL: <Link color="inherit" href={`http://${host}:${httpPort}/`}>
                            http://{host}:{httpPort}/
                        </Link>
                        </Typography>

                        <Typography variant="body2" color="textSecondary" sx={{mt: 2}}>
                            WebSocket URL: ws://{host}:{httpPort}/websocket/connect
                        </Typography>

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
    );
};

