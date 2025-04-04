import React from 'react';
import {PaperbaseContent} from "@/layout/paperbase_theme/PaperbaseContent";
import {Provider} from "react-redux";
import {AppStateStore} from "@/store/AppStateStore";
import {LatestImagesContextProvider} from "@/context/latest-images-context/LatestImagesContext";
import {WebSocketContextProvider} from "@/context/websocket-context/WebSocketContext";


function App() {
    const _port = 8006;
    const wsUrl = `ws://localhost:${_port}/skellycam/websocket/connect`;


    return (
        <Provider store={AppStateStore}>
            <LatestImagesContextProvider>
                <WebSocketContextProvider url={wsUrl}>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
            </LatestImagesContextProvider>
        </Provider>
    );
}

export default App;
