import React, {createContext, ReactNode, useContext} from "react";
import { useWebSocket} from "@/context/websocket-context/useWebSocket";
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import * as THREE from "three";


interface WebSocketContextProps {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    latestImageData: Record<string, CameraImageData>;
    registerCameraViewTexture:(cameraId: string, texture: THREE.VideoFrameTexture)=> void;
}


interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}

const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketContextProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const { isConnected, connect, disconnect, latestImageData,registerCameraViewTexture } = useWebSocket(url);

    return (
        <WebSocketContext.Provider value={{isConnected, connect, disconnect,latestImageData,registerCameraViewTexture}}>
            {children}
        </WebSocketContext.Provider>
    )
}

export const useWebSocketContext = () => {
    const context = useContext(WebSocketContext);
    if (!context) {
        throw new Error('useWebSocketContext must be used within a WebSocketProvider');
    }
    return context;
};
