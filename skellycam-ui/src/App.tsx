import React, {useEffect} from 'react';
import {PaperbaseContent} from "@/layout/paperbase_theme/PaperbaseContent";
import {WebSocketContextProvider} from "@/services/websocket-connection/WebSocketContext";
import {Provider} from "react-redux";
import {AppStateStore, useAppDispatch} from "@/store/AppStateStore";
import {detectBrowserDevices} from "@/store/thunks/camera-thunks";


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
