import { useState, useCallback } from "react";

export const usePythonServer = () => {
    const [isRunning, setIsRunning] = useState(false);

    const startServer = useCallback(async () => {
        try {
            console.log("Starting Python server...");
            window.electronAPI.startPythonServer();
            setIsRunning(true);
        } catch (error) {
            console.error('Failed to start Python server:', error);
        }
    }, []);

    const stopServer = useCallback(async () => {
        try {
            console.log("Stopping Python server...");
            window.electronAPI.stopPythonServer();
            setIsRunning(false);
        } catch (error) {
            console.error('Failed to stop Python server:', error);
        }
    }, []);

    return {
        isRunning,
        startServer,
        stopServer
    };
};
