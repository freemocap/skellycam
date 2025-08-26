import {useCallback, useEffect, useState} from "react";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {serverHealthcheck} from "@/store/thunks/server-healthcheck";
import {shutdownServer} from "@/store/thunks/shutdown-server";

export type ServerStatus = 'not-connected' | 'spawning' | 'alive' | 'error';

export const usePythonServer = () => {
    const {isConnected, connect} = useWebSocketContext()
    const [serverStatus, setServerStatus] = useState<ServerStatus>('not-connected');
    const [errorMessage, setErrorMessage] = useState<string | null>(null);


    const checkServerHealth = useCallback(async () => {

        const maxRetries = 10;
        const retryDelay = 3000; // ms

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                if (isConnected) {
                    // If websocket is connected, we can assume server is alive

                    setServerStatus('alive');
                    setErrorMessage(null);
                    return true;
                }
                const response = await serverHealthcheck();

                if (response?.ok) {
                    setServerStatus('alive');
                    setErrorMessage(null);
                    return true;
                }

                // If not the last attempt, wait before retrying
                if (attempt < maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, retryDelay));
                }
            } catch (error) {
                // If not the last attempt, wait before retrying
                if (attempt < maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, retryDelay));
                } else {
                    // Last attempt failed
                    setServerStatus('not-connected');
                    setErrorMessage(null);
                    return false;
                }
            }
        }

        // All attempts failed
        setServerStatus('error');
        setErrorMessage(`Health check failed after ${maxRetries} attempts`);
        return false;
    }, [isConnected]);

    const startPythonServer = useCallback(async (exePath: string | null) => {
        try {
            setErrorMessage(null);
            console.log("Starting Python server...");
            try {
                await shutdownServer()

            } catch (error) {
                console.log("Error sending shutdown signal", error)
            }
            setServerStatus('spawning');

            await window.electronAPI.startPythonServer(exePath);

            // Start health checks only if websocket is not connected
            if (!isConnected) {
                setTimeout(() => checkServerHealth(), 1000);
            } else {
                setServerStatus('alive');
            }
        } catch (error) {
            setServerStatus('error');
            setErrorMessage(`Failed to start server: ${error}`);
            console.error('Failed to start Python server:', error);
        }
    }, [checkServerHealth, isConnected]);

    const stopPythonServer = useCallback(async () => {
        try {
            console.log("Stopping Python server...");
            try {
                await shutdownServer()

            } catch (error) {
                console.log("Error sending shutdown signal", error)
            }

            await window.electronAPI.stopPythonServer();
            setServerStatus('not-connected');
            setErrorMessage(null);
        } catch (error) {
            setServerStatus('error');
            setErrorMessage(`Failed to stop server: ${error}`);
            console.error('Failed to stop Python server:', error);
        }
    }, []);

    // Auto-start server on mount if it's not already running
    useEffect(() => {
        const autoStartServer = async () => {

            // Check if server is already running or being spawned
            if (serverStatus === 'alive' || serverStatus === 'spawning'|| isConnected) {
                return;
            }
            try{
                connect()
                return; // If connect() doesn't throw, we're connected
            } catch(error){
                console.log("Server not connected, spawning server process...")
            }
            // Check if there's a current executable path
            try {
                const currentPath = await window.electronAPI.getPythonServerExecutablePath();
                if (currentPath) {
                    console.log("Auto-starting Python server with path:", currentPath);
                    startPythonServer(currentPath);
                } else {
                    // Try to find a valid candidate
                    const candidates = await window.electronAPI.getPythonServerExecutableCandidates();
                    const validCandidate = candidates.find(c => c.isValid);
                    if (validCandidate) {
                        console.log("Auto-starting Python server with candidate:", validCandidate.path);
                        startPythonServer(validCandidate.path);
                    }
                }
            } catch (error) {
                console.log("Error during auto-start:", error);
            }
        };

        // Small delay to allow context to initialize
        const timeoutId = setTimeout(() => {
            autoStartServer();
        }, 3000);

        return () => clearTimeout(timeoutId);
    }, []); // Run only once on mount

    useEffect(() => {
        if (!isConnected) {
            checkServerHealth()
            return () => {
            };
        } else {
            // If websocket is connected, server is alive
            setServerStatus('alive');
            setErrorMessage(null);
        }
    }, [isConnected, checkServerHealth]);

    return {
        serverStatus,
        errorMessage,
        isPythonRunning: serverStatus === 'alive',
        startPythonServer,
        stopPythonServer
    };
};
