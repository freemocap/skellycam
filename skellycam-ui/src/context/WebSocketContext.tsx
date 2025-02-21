import React, {createContext, ReactNode, useContext} from "react";
import {useWebSocket} from "@/hooks/useWebSocket";
import {z} from "zod";
import {FrontendFramePayloadSchema, JpegImagesSchema} from "@/types/zod-schemas/FrontendFramePayloadSchema";
import {SkellyCamAppStateSchema} from "@/types/zod-schemas/SkellyCamAppStateSchema";

interface WebSocketContextProps {
    isConnected: boolean;
    latestFrontendPayload: z.infer<typeof FrontendFramePayloadSchema> | null;
    latestSkellyCamAppState: z.infer<typeof SkellyCamAppStateSchema> | null;
    latestImages:z.infer<typeof JpegImagesSchema> |null;
    latestLogs: object[] | null;
    connect: () => void;
    disconnect: () => void;
}

interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}

const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketContextProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const {isConnected, latestFrontendPayload,  latestImages, latestSkellyCamAppState, latestLogs, connect, disconnect} = useWebSocket(url);

    return (
        <WebSocketContext.Provider value={{isConnected, latestFrontendPayload,latestImages, latestSkellyCamAppState, latestLogs, connect, disconnect}}>
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
