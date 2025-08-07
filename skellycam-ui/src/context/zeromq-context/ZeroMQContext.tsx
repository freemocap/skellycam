// skellycam-ui/src/context/zeromq-context/ZeroMQContext.tsx
import React, { createContext, useContext, useEffect } from 'react';
import { useZeroMQ } from './useZeroMQ';
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {urlService} from "@/services/urlService";

interface ZeroMQContextType {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
}

const ZeroMQContext = createContext<ZeroMQContextType | undefined>(undefined);

export const ZeroMQProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const zeromqUrl = urlService.getZeroMQUrl('5555'); // Default ZeroMQ port
    const { isConnected, connect, disconnect } = useZeroMQ(zeromqUrl);

    useEffect(() => {
        // Auto-connect when the provider is mounted
        connect();

        // Disconnect when the provider is unmounted
        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    return (
        <ZeroMQContext.Provider value={{ isConnected, connect, disconnect }}>
            {children}
        </ZeroMQContext.Provider>
    );
};

export const useZeroMQContext = (): ZeroMQContextType => {
    const context = useContext(ZeroMQContext);
    if (context === undefined) {
        throw new Error('useZeroMQContext must be used within a ZeroMQProvider');
    }
    return context;
};
