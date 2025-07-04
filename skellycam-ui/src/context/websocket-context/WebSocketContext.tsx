import React, {createContext, ReactNode, useContext} from "react";
import {useWebSocket} from "@/context/websocket-context/useWebSocket";

interface WebSocketContextProps {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    latestImageBitmaps: Record<string, ImageBitmap>;
}


interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}

const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketContextProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const {isConnected, connect, disconnect, latestImageBitmaps} = useWebSocket(url);

    return (
        <WebSocketContext.Provider value={{isConnected, connect, disconnect,latestImageBitmaps}}>
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
