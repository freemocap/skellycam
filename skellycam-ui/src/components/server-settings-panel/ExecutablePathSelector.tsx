// components/ExecutablePathSelector.tsx
import React, { useState, useEffect } from 'react';
import {
    Box,
    Button,
    FormControl,
    FormControlLabel,
    Radio,
    RadioGroup,
    Stack,
    Typography,
    CircularProgress,
} from '@mui/material';
import {
    useAppDispatch,
    useAppSelector,
    selectExecutableCandidates,
    selectHasManagedServer,
    selectConnectionStatus,
    selectManagedProcess,
    selectIsRefreshingExecutables,
    selectPreferredExecutablePath,
    refreshExecutableCandidates,
    startManagedServer,
    stopManagedServer,
    updateServerConfig,
} from "@/store";
import { useElectronIPC } from "@/services/electron-ipc/electron-ipc";

export const ExecutablePathSelector: React.FC = () => {
    const dispatch = useAppDispatch();
    const { api, isElectron } = useElectronIPC();

    // Redux selectors
    const candidates = useAppSelector(selectExecutableCandidates);
    const hasManagedServer = useAppSelector(selectHasManagedServer);
    const connectionStatus = useAppSelector(selectConnectionStatus);
    const managedProcess = useAppSelector(selectManagedProcess);
    const isRefreshing = useAppSelector(selectIsRefreshingExecutables);
    const preferredPath = useAppSelector(selectPreferredExecutablePath);

    // Local state for selected path
    const [selectedPath, setSelectedPath] = useState<string | null>(preferredPath);

    useEffect(() => {
        // Load executables on mount if in Electron
        if (isElectron && candidates.length === 0) {
            dispatch(refreshExecutableCandidates());
        }
    }, [isElectron, dispatch]);

    useEffect(() => {
        // Update selected path when preferred path changes
        setSelectedPath(preferredPath);
    }, [preferredPath]);

    const handleSelectCustom = async () => {
        if (!api) return;

        try {
            const path = await api.fileSystem.selectExecutableFile.mutate();
            if (path) {
                setSelectedPath(path);
                dispatch(updateServerConfig({ preferredExecutablePath: path }));
            }
        } catch (error) {
            console.error('Failed to select custom executable:', error);
        }
    };

    const handleStartServer = () => {
        dispatch(startManagedServer({ executablePath: selectedPath }));
    };

    const handleStopServer = () => {
        dispatch(stopManagedServer());
    };

    const handleRefresh = () => {
        dispatch(refreshExecutableCandidates());
    };

    const handlePathChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const path = event.target.value;
        setSelectedPath(path);
        dispatch(updateServerConfig({ preferredExecutablePath: path }));
    };

    if (!isElectron) {
        return (
            <Box p={2}>
                <Typography variant="body1" color="text.secondary">
                    Executable management is only available in the desktop app
                </Typography>
            </Box>
        );
    }

    const isRunning = connectionStatus === 'connected' && hasManagedServer;
    const isTransitioning = connectionStatus === 'connecting' || connectionStatus === 'disconnecting';

    return (
        <Stack spacing={3} p={2}>
            <Box display="flex" alignItems="center" justifyContent="space-between">
                <Typography variant="h6">
                    Python Server: {isRunning ? '🟢 Running' : '🔴 Stopped'}
                </Typography>
                {isRefreshing && <CircularProgress size={20} />}
            </Box>

            {managedProcess && (
                <Box>
                    <Typography variant="caption" color="text.secondary">
                        PID: {managedProcess.pid || 'Unknown'}
                    </Typography>
                </Box>
            )}

            <Box>
                <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                    <Typography variant="subtitle2">Available Executables</Typography>
                    <Button size="small" onClick={handleRefresh} disabled={isRefreshing}>
                        Refresh
                    </Button>
                </Box>

                <FormControl component="fieldset" fullWidth>
                    <RadioGroup value={selectedPath || ''} onChange={handlePathChange}>
                        {candidates.map((candidate) => (
                            <FormControlLabel
                                key={candidate.path}
                                value={candidate.path}
                                control={<Radio />}
                                disabled={!candidate.isValid || isTransitioning}
                                label={
                                    <Box>
                                        <Typography variant="body2">
                                            {candidate.name}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {candidate.description}
                                            {!candidate.isValid && ` (${candidate.error})`}
                                        </Typography>
                                    </Box>
                                }
                            />
                        ))}
                    </RadioGroup>
                </FormControl>
            </Box>

            <Stack direction="row" spacing={2}>
                <Button
                    variant="outlined"
                    onClick={handleSelectCustom}
                    disabled={isTransitioning}
                    fullWidth
                >
                    Browse...
                </Button>

                {isRunning ? (
                    <Button
                        variant="contained"
                        color="error"
                        onClick={handleStopServer}
                        disabled={isTransitioning}
                        fullWidth
                    >
                        Stop Server
                    </Button>
                ) : (
                    <Button
                        variant="contained"
                        color="primary"
                        onClick={handleStartServer}
                        disabled={isTransitioning || !selectedPath}
                        fullWidth
                    >
                        Start Server
                    </Button>
                )}
            </Stack>
        </Stack>
    );
};
