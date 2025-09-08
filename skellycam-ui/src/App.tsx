
import React, { useEffect } from 'react';
import { Provider } from 'react-redux';
import { store } from '@/store';
import { websocketService } from '@/services/websocket/websocket-service';
import { PaperbaseContent } from '@/layout/paperbase_theme/PaperbaseContent';

function AppContent() {
    useEffect(() => {
        // Initialize WebSocket service once
        websocketService.initialize();
    }, []);

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
