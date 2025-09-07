import React, { useEffect } from 'react';
import { Provider } from "react-redux";
import { store } from "@/store/store";
import { PaperbaseContent } from "@/layout/paperbase_theme/PaperbaseContent";
import { useAppSelector } from '@/store/hooks';
import { selectServerStatus } from '@/store/slices/server/server-selectors';
import {websocketManager} from "@/services/api";

function AppContent() {
    const serverStatus = useAppSelector(selectServerStatus);

    useEffect(() => {
        // Auto-connect WebSocket when server is alive
        if (serverStatus === 'alive') {
            const wsUrl = `ws://localhost:8006/skellycam/websocket/connect`;
            websocketManager.connect(wsUrl);
        } else if (serverStatus === 'not-connected') {
            websocketManager.disconnect();
        }
    }, [serverStatus]);

    return <PaperbaseContent />;
}

function App() {
    return (
        <Provider store={store}>
            <AppContent />
        </Provider>
    );
}

export default App;
