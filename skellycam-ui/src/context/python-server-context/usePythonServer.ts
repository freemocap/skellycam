import { urlService } from "@/config/appUrlService";
import {useCallback, useEffect, useRef, useState} from "react";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

export type ServerStatus = 'not-connected' | 'spawning' | 'alive' | 'error';

export const usePythonServer = () => {
    const {isConnected} = useWebSocketContext()
    const [serverStatus, setServerStatus] = useState<ServerStatus>('not-connected');
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const healthCheckInterval = useRef<NodeJS.Timeout | null>(null);

    const checkServerHealth = useCallback(async () => {
        if (isConnected){
            return true
        }
        try {
            const response = await fetch(urlService.getHttpEndpointUrls().health, {
                method: 'GET',
                signal: AbortSignal.timeout(2000) // 2 second timeout
            });
            
            if (response.ok) {
                setServerStatus('alive');
                setErrorMessage(null);
                return true;
            } else {
                setServerStatus('error');
                setErrorMessage(`Health check failed: ${response.status}`);
                return false;
            }
        } catch (error) {
            setServerStatus('not-connected');
            setErrorMessage(null);
            return false;
        }
    }, [isConnected]);

    const startPythonServer = useCallback(async (exePath: string | null) => {
        try {
            setServerStatus('spawning');
            setErrorMessage(null);
            console.log("Starting Python server...");
            await window.electronAPI.startPythonServer(exePath);
            
            // Start health checks
            healthCheckInterval.current = setInterval(checkServerHealth, 2000);
            
            // Do initial check after a short delay
            setTimeout(() => checkServerHealth(), 500);
        } catch (error) {
            setServerStatus('error');
            setErrorMessage(`Failed to start server: ${error}`);
            console.error('Failed to start Python server:', error);
        }
    }, [checkServerHealth]);

    const stopPythonServer = useCallback(async () => {
        try {
            console.log("Stopping Python server...");
            
            // Stop health checks
            if (healthCheckInterval.current) {
                clearInterval(healthCheckInterval.current);
                healthCheckInterval.current = null;
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

    // Start health checks if server might be running
    useEffect(() => {
        checkServerHealth();
        
        return () => {
            if (healthCheckInterval.current) {
                clearInterval(healthCheckInterval.current);
            }
        };
    }, []);

    return {
        serverStatus,
        errorMessage,
        isPythonRunning: serverStatus === 'alive',
        startPythonServer,
        stopPythonServer
    };
};