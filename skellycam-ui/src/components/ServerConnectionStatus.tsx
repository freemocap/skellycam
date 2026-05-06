import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from "react-i18next";
import { useElectronIPC } from '@/services';
import { DEFAULT_HOST, DEFAULT_PORT } from '@/services/server/server-helpers/server-urls';
import DropdownButton from './ui-components/DropdownButton';
import ToggleButtonComponent from './ui-components/ToggleButtonComponent';
import { STATES } from './ui-components/states';
import { ConnectionSettingsModal } from './ConnectionSettingsModal';

export interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
    resolvedPath?: string;
}

const WS_RECONNECT_INTERVAL_MS = 3000;

const STORAGE_KEYS = {
    SELECTED_EXE_PATH: 'skellycam:selectedExePath',
    AUTO_LAUNCH_SERVER: 'skellycam:autoLaunchServer',
    AUTO_CONNECT_WS: 'skellycam:autoConnectWs',
    SERVER_HOST: 'skellycam:serverHost',
    SERVER_PORT: 'skellycam:serverPort',
} as const;

function loadFromStorage<T>(key: string, fallback: T): T {
    try {
        const raw = localStorage.getItem(key);
        if (raw === null) return fallback;
        return JSON.parse(raw) as T;
    } catch {
        return fallback;
    }
}

function saveToStorage(key: string, value: unknown): void {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (err) {
        console.error(`Failed to save ${key} to localStorage:`, err);
    }
}

export const ServerConnectionStatus: React.FC = () => {
    const { isConnected, connect, disconnect, connectedCameraIds, updateServerConnection } = useServer();
    const { t } = useTranslation();
    const { isElectron, api } = useElectronIPC();

    // Persisted UI state
    const [selectedExePath, setSelectedExePath] = useState(() => loadFromStorage(STORAGE_KEYS.SELECTED_EXE_PATH, ''));
    const [autoLaunchServer, setAutoLaunchServer] = useState(() => loadFromStorage(STORAGE_KEYS.AUTO_LAUNCH_SERVER, true));
    const [autoConnectWs, setAutoConnectWs] = useState(() => loadFromStorage(STORAGE_KEYS.AUTO_CONNECT_WS, true));
    const [serverHost, setServerHost] = useState(() => loadFromStorage(STORAGE_KEYS.SERVER_HOST, DEFAULT_HOST));
    const [serverPort, setServerPort] = useState(() => loadFromStorage(STORAGE_KEYS.SERVER_PORT, DEFAULT_PORT));

    const [hostDraft, setHostDraft] = useState(serverHost);
    const [portDraft, setPortDraft] = useState(String(serverPort));

    // Transient state
    const [serverRunning, setServerRunning] = useState(false);
    const [serverLoading, setServerLoading] = useState(false);
    const [currentExePath, setCurrentExePath] = useState<string | null>(null);
    const [candidates, setCandidates] = useState<ExecutableCandidate[]>([]);
    const [candidatesLoading, setCandidatesLoading] = useState(false);
    const [processInfo, setProcessInfo] = useState<{ pid: number | undefined; killed: boolean } | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [settingsOpen, setSettingsOpen] = useState(false);

    const autoLaunchFiredRef = useRef(false);
    const serverLaunchingRef = useRef(false);

    // ── Persistence effects ──

    useEffect(() => { saveToStorage(STORAGE_KEYS.SELECTED_EXE_PATH, selectedExePath); }, [selectedExePath]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.AUTO_LAUNCH_SERVER, autoLaunchServer); }, [autoLaunchServer]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.AUTO_CONNECT_WS, autoConnectWs); }, [autoConnectWs]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.SERVER_HOST, serverHost); }, [serverHost]);
    useEffect(() => { saveToStorage(STORAGE_KEYS.SERVER_PORT, serverPort); }, [serverPort]);

    useEffect(() => {
        updateServerConnection(serverHost, serverPort);
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Server status polling ──

    const pollServerStatus = useCallback(async () => {
        if (!isElectron || !api) return;
        try {
            const running = await api.pythonServer.isRunning.query();
            setServerRunning(running);
            const info = await api.pythonServer.getProcessInfo.query();
            setProcessInfo(info);
            const exePath = await api.pythonServer.getExecutablePath.query();
            setCurrentExePath(exePath);
        } catch (err) {
            console.error('Failed to poll server status:', err);
        }
    }, [isElectron, api]);

    // ── Candidate management ──

    const loadCandidates = useCallback(async () => {
        if (!isElectron || !api) return;
        setCandidatesLoading(true);
        try {
            const result = await api.pythonServer.getExecutableCandidates.query();
            const typed = result as ExecutableCandidate[];
            setCandidates(typed);
            if (!selectedExePath) {
                const firstValid = typed.find((c) => c.isValid);
                if (firstValid) setSelectedExePath(firstValid.path);
            }
        } catch (err) {
            console.error('Failed to load executable candidates:', err);
            setError(`Failed to load candidates: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setCandidatesLoading(false);
        }
    }, [isElectron, api, selectedExePath]);

    const refreshCandidates = useCallback(async () => {
        if (!isElectron || !api) return;
        setCandidatesLoading(true);
        setError(null);
        try {
            const result = await api.pythonServer.refreshCandidates.mutate();
            const typed = result as ExecutableCandidate[];
            setCandidates(typed);
            const firstValid = typed.find((c) => c.isValid);
            if (firstValid) setSelectedExePath(firstValid.path);
        } catch (err) {
            console.error('Failed to refresh candidates:', err);
            setError(`Failed to refresh: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setCandidatesLoading(false);
        }
    }, [isElectron, api]);

    const browseForExecutable = useCallback(async () => {
        if (!isElectron || !api) return;
        try {
            const filePath = await api.fileSystem.selectExecutableFile.mutate();
            if (filePath) setSelectedExePath(filePath);
        } catch (err) {
            console.error('Failed to browse for executable:', err);
            setError(`Browse failed: ${err instanceof Error ? err.message : String(err)}`);
        }
    }, [isElectron, api]);

    // ── Server actions ──

    const startServer = useCallback(async () => {
        if (!isElectron || !api) return;
        if (serverLaunchingRef.current) return;
        serverLaunchingRef.current = true;
        setServerLoading(true);
        setError(null);
        try {
            await api.pythonServer.start.mutate({ exePath: selectedExePath || null });
            await pollServerStatus();
        } catch (err) {
            console.error('Failed to start server:', err);
            setError(`Start failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setServerLoading(false);
            serverLaunchingRef.current = false;
        }
    }, [isElectron, api, selectedExePath, pollServerStatus]);

    const stopServer = useCallback(async () => {
        if (!isElectron || !api) return;
        setServerLoading(true);
        setError(null);
        try {
            disconnect();
            await api.pythonServer.stop.mutate();
            await pollServerStatus();
        } catch (err) {
            console.error('Failed to stop server:', err);
            setError(`Stop failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setServerLoading(false);
        }
    }, [isElectron, api, pollServerStatus, disconnect]);

    const resetServer = useCallback(async () => {
        if (!isElectron || !api) return;
        setServerLoading(true);
        setError(null);
        try {
            disconnect();
            await api.pythonServer.stop.mutate();
            await new Promise((resolve) => setTimeout(resolve, 500));
            await api.pythonServer.start.mutate({ exePath: selectedExePath || null });
            await pollServerStatus();
        } catch (err) {
            console.error('Failed to reset server:', err);
            setError(`Reset failed: ${err instanceof Error ? err.message : String(err)}`);
        } finally {
            setServerLoading(false);
        }
    }, [isElectron, api, selectedExePath, pollServerStatus, disconnect]);

    // ── Effects ──

    useEffect(() => {
        if (isElectron && api) {
            pollServerStatus();
            loadCandidates();
        }
    }, [isElectron, api, pollServerStatus, loadCandidates]);

    useEffect(() => {
        if (!isElectron || !api) return;
        const interval = setInterval(pollServerStatus, 5000);
        return () => clearInterval(interval);
    }, [isElectron, api, pollServerStatus]);

    useEffect(() => {
        if (!isElectron || !api) return;
        if (!autoLaunchServer) return;
        if (autoLaunchFiredRef.current) return;
        if (candidatesLoading) return;
        if (serverRunning || serverLoading) return;
        autoLaunchFiredRef.current = true;
        console.log('Auto-launching server...');
        startServer();
    }, [isElectron, api, autoLaunchServer, candidatesLoading, serverRunning, serverLoading, startServer]);

    useEffect(() => {
        if (!autoConnectWs) return;
        if (isConnected) return;
        connect();
        const interval = setInterval(() => {
            if (!isConnected) connect();
        }, WS_RECONNECT_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [autoConnectWs, isConnected, connect]);

    // ── Toggle handlers ──

    const handleToggleAutoLaunch = useCallback((newState: boolean) => {
        setAutoLaunchServer(newState);
    }, []);

    const handleToggleAutoConnectWs = useCallback((newState: boolean) => {
        setAutoConnectWs(newState);
        if (!newState) disconnect();
    }, [disconnect]);

    const handleToggleWsConnected = useCallback(() => {
        if (isConnected) {
            setAutoConnectWs(false);
            disconnect();
        } else {
            setAutoConnectWs(true);
            connect();
        }
    }, [isConnected, connect, disconnect]);

    const applyHostPort = useCallback(() => {
        const trimmedHost = hostDraft.trim();
        const parsedPort = parseInt(portDraft, 10);
        if (!trimmedHost) return;
        if (isNaN(parsedPort) || parsedPort < 1 || parsedPort > 65535) return;
        setServerHost(trimmedHost);
        setServerPort(parsedPort);
        updateServerConnection(trimmedHost, parsedPort);
    }, [hostDraft, portDraft, updateServerConnection]);

    const handleHostPortKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter') applyHostPort();
    }, [applyHostPort]);

    // ── Derived connection states ──

    const serverState = serverRunning ? STATES.CONNECTED : serverLoading ? STATES.CONNECTING : STATES.DISCONNECTED;
    const wsState = isConnected ? STATES.CONNECTED : autoConnectWs ? STATES.CONNECTING : STATES.DISCONNECTED;

    const getOverallStatus = () => {
        const states = isElectron ? [serverState, wsState] : [wsState];
        if (states.every((s) => s === STATES.CONNECTED)) return { text: t('connected'), iconClass: 'connected-icon' };
        if (states.some((s) => s === STATES.CONNECTING)) return { text: t('connecting'), iconClass: 'loader-icon' };
        if (states.some((s) => s === STATES.CONNECTED)) return { text: 'Partially Connected', iconClass: 'connected-icon' };
        return { text: 'Not Connected', iconClass: 'warning-icon' };
    };

    const overallStatus = getOverallStatus();
    const cameraCountSuffix = isConnected && connectedCameraIds.length > 0
        ? ` (${connectedCameraIds.length} cam${connectedCameraIds.length !== 1 ? 's' : ''})`
        : '';

    const rowIconClass = (state: string) => {
        if (state === STATES.CONNECTED) return 'connected-icon';
        if (state === STATES.CONNECTING) return 'loader-icon';
        return 'warning-icon';
    };

    const toggleConfig = {
        connectConfig: { text: 'Connect', extraClasses: '' },
        connectingConfig: { text: 'Connecting...', extraClasses: 'loading disabled' },
        connectedConfig: { text: 'Connected', extraClasses: 'activated' },
    };

    // ── Render ──

    return (
        <>
            <DropdownButton
                buttonProps={{
                    text: overallStatus.text + cameraCountSuffix,
                    iconClass: overallStatus.iconClass,
                    rightSideIcon: 'dropdown',
                    textColor: 'text-gray',
                }}
                dropdownItems={
                    <div className="connection-container flex flex-col p-1 gap-1 br-1 bg-darkgray border-1 border-mid-black">
                        {/* Python server row (Electron only) */}
                        {isElectron && (
                            <div className="gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                                <div className="text-container overflow-hidden flex items-center gap-1">
                                    <span className={`icon icon-size-16 ${rowIconClass(serverState)}`} />
                                    <p className="text text-nowrap text-left bg">Python server</p>
                                </div>
                                <ToggleButtonComponent
                                    state={serverState}
                                    {...toggleConfig}
                                    textColor="text-white"
                                    onConnect={startServer}
                                    onDisconnect={stopServer}
                                />
                            </div>
                        )}

                        {/* WebSocket row */}
                        <div className="gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                            <div className="text-container overflow-hidden flex items-center gap-1">
                                <span className={`icon icon-size-16 ${rowIconClass(wsState)}`} />
                                <p className="text text-nowrap text-left bg">Websocket</p>
                            </div>
                            <ToggleButtonComponent
                                state={wsState}
                                {...toggleConfig}
                                textColor="text-white"
                                onConnect={() => { setAutoConnectWs(true); connect(); }}
                                onDisconnect={() => { setAutoConnectWs(false); disconnect(); }}
                            />
                        </div>

                        {/* Footer: help text + settings trigger */}
                        <div className="flex flex-row p-1 gap-1 items-center justify-content-space-between">
                            <p className="text-left text">Having trouble connecting? Learn how to connect...</p>
                            <button
                                className="button icon-button"
                                onClick={(e) => { e.stopPropagation(); setSettingsOpen(true); }}
                            >
                                <span className="icon settings-icon icon-size-16" />
                            </button>
                        </div>
                    </div>
                }
            />
            <ConnectionSettingsModal
                open={settingsOpen}
                onClose={() => setSettingsOpen(false)}
                isElectron={isElectron}
                autoLaunchServer={autoLaunchServer}
                handleToggleAutoLaunch={handleToggleAutoLaunch}
                serverRunning={serverRunning}
                serverLoading={serverLoading}
                processInfo={processInfo}
                candidates={candidates}
                candidatesLoading={candidatesLoading}
                selectedExePath={selectedExePath}
                setSelectedExePath={setSelectedExePath}
                browseForExecutable={browseForExecutable}
                refreshCandidates={refreshCandidates}
                startServer={startServer}
                stopServer={stopServer}
                resetServer={resetServer}
                currentExePath={currentExePath}
                error={error}
                isConnected={isConnected}
                autoConnectWs={autoConnectWs}
                handleToggleAutoConnectWs={handleToggleAutoConnectWs}
                connectedCameraIds={connectedCameraIds}
                hostDraft={hostDraft}
                portDraft={portDraft}
                setHostDraft={setHostDraft}
                setPortDraft={setPortDraft}
                applyHostPort={applyHostPort}
                handleHostPortKeyDown={handleHostPortKeyDown}
                handleToggleWsConnected={handleToggleWsConnected}
            />
        </>
    );
};
