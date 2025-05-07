import React from 'react';
import {PaperbaseContent} from "@/layout/paperbase_theme/PaperbaseContent";
import {Provider} from "react-redux";
import {AppStateStore} from "@/store/AppStateStore";
import {WebSocketContextProvider} from "@/context/websocket-context/WebSocketContext";


function App() {
    const _port = 8006;
    const wsUrl = `ws://localhost:${_port}/skellycam/websocket/connect`;


    return (
        <Provider store={AppStateStore}>
                <WebSocketContextProvider url={wsUrl}>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
        </Provider>
    );
}

export default App;
