import React from 'react';
import {Provider} from 'react-redux';
import {store} from '@/store';
import {WebSocketProvider} from "@/services/websocket/WebsocketContextProvider";
import {PaperbaseContent} from "@/layout/paperbase_theme/PaperbaseContent";


function App() {
    return (
        <Provider store={store}>
            <WebSocketProvider>
                <PaperbaseContent/>
            </WebSocketProvider>
        </Provider>
    );
}

export default App;
