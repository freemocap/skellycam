import React, { createContext, ReactNode, useContext } from "react";
import { ServerStatus, usePythonServer } from "./usePythonServer";

interface PythonServerContextProps {
    serverStatus: ServerStatus;
    errorMessage: string | null;
    isPythonRunning: boolean;
    isTransitioning: boolean;
    retryCount: number;
    lastHealthCheck: Date | null;
    startPythonServer: (exePath: string | null) => Promise<boolean>;
    stopPythonServer: () => Promise<boolean>;
    checkServerHealth: () => Promise<boolean>;
}

const PythonServerContext = createContext<PythonServerContextProps | undefined>(undefined);

interface PythonServerProviderProps {
    children: ReactNode;
}

export const PythonServerContextProvider: React.FC<PythonServerProviderProps> = ({ children }) => {
    const pythonServer = usePythonServer();

    return (
        <PythonServerContext.Provider value={pythonServer}>
            {children}
        </PythonServerContext.Provider>
    );
};

export const usePythonServerContext = () => {
    const context = useContext(PythonServerContext);
    if (!context) {
        throw new Error('usePythonServerContext must be used within a PythonServerProvider');
    }
    return context;
};
