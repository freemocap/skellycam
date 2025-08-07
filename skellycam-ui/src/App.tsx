import React from 'react';
import { PaperbaseContent } from "@/layout/paperbase_theme/PaperbaseContent";
import { Provider } from "react-redux";
import { AppStateStore } from "@/store/AppStateStore";
import { WebSocketContextProvider } from "@/context/websocket-context/WebSocketContext";
import { urlService } from '@/services/urlService';
import {ZeroMQProvider} from "@/context/zeromq-context/ZeroMQContext";

function App() {
    return (
        <Provider store={AppStateStore}>
            <ZeroMQProvider>
                <WebSocketContextProvider>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
            </ZeroMQProvider>
        </Provider>
    );
}

export default App;

