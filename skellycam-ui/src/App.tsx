import React from 'react';
import { PaperbaseContent } from "@/layout/paperbase_theme/PaperbaseContent";
import { Provider } from "react-redux";
import { AppStateStore } from "@/store/AppStateStore";
import { WebSocketContextProvider } from "@/contexts/websocket-context/WebSocketContext";
import { urlService } from '@/services/urlService';
import {GrpcContextProvider} from "@/contexts/grpc-context/GrcpContext";

function App() {
    const wsUrl = urlService.getWebSocketUrl();
    const grpcUrl = urlService.getGrpcServerUrl();
    return (
        <Provider store={AppStateStore}>
            <GrpcContextProvider url={grpcUrl}>
                <WebSocketContextProvider url={wsUrl}>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
            </GrpcContextProvider>
        </Provider>
    );
}

export default App;

