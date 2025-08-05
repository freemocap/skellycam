import React, { createContext, ReactNode, useContext } from 'react';
import {CameraImageData} from "@/contexts/websocket-context/useWebsocketBinaryMessageProcessor";
import {useGrpcClient} from "@/contexts/grpc-context/useGrpc";

interface GrpcContextProps {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    latestImageData: Record<string, CameraImageData>;
    acknowledgeFrameRendered: (cameraId: string, frameNumber: number) => void;
}

interface GrpcProviderProps {
    url: string;
    children: ReactNode;
}

const GrpcContext = createContext<GrpcContextProps | undefined>(undefined);

export const GrpcContextProvider: React.FC<GrpcProviderProps> = ({ url, children }) => {
    const { isConnected, connect, disconnect, latestImageData, acknowledgeFrameRendered } = useGrpcClient(url);

    return (
        <GrpcContext.Provider value={{ isConnected, connect, disconnect, latestImageData, acknowledgeFrameRendered }}>
            {children}
        </GrpcContext.Provider>
    );
};

export const useGrpcContext = () => {
    const context = useContext(GrpcContext);
    if (!context) {
        throw new Error('useGrpcContext must be used within a GrpcProvider');
    }
    return context;
};
