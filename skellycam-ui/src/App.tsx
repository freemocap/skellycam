import React from 'react';
import { PaperbaseContent } from "@/layout/paperbase_theme/PaperbaseContent";
import { Provider } from "react-redux";
import { AppStateStore } from "@/store/AppStateStore";
import { WebSocketContextProvider } from "@/context/websocket-context/WebSocketContext";
import { urlService } from '@/services/urlService';
import { LmdbContextProvider } from './context/lmdb-context/LmdbContext';

function App() {
    const wsUrl = urlService.getWebSocketUrl();
    return (
        <Provider store={AppStateStore}>
            <LmdbContextProvider>
                <WebSocketContextProvider url={wsUrl}>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
            </LmdbContextProvider>
        </Provider>
    );
}

export default App;

