import React, {createContext, ReactNode, useContext} from "react";
import {FrameRenderAcknowledgment, useWebSocket} from "@/context/websocket-context/useWebSocket";
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";


interface WebSocketContextProps {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    latestImageData: Record<string, CameraImageData>;
    sendFrameAcknowledgment:(cameraId: string, frameNumber: number, imageDisplayWidth:number, imageDisplayHeight:number)=> void;
}


interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}

const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketContextProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const { isConnected, connect, disconnect, latestImageData, sendFrameAcknowledgment } = useWebSocket(url);

    return (
        <WebSocketContext.Provider value={{isConnected, connect, disconnect,latestImageData, sendFrameAcknowledgment}}>
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
