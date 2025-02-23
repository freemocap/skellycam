import React from 'react';
import {PaperbaseContent} from "@/layout/paperbase_theme/PaperbaseContent";
import {WebSocketContextProvider} from "@/context/WebSocketContext";
import {Provider} from "react-redux";
import {AppStateStore} from "@/store/appStateStore";
import {CameraProvider} from "@/context/detectedDevicesContext";


function App() {
    const _port = 8006;
    const wsUrl = `ws://localhost:${_port}/skellycam/websocket/connect`;
    return (

        <Provider store={AppStateStore}>
            <CameraProvider>
                <WebSocketContextProvider url={wsUrl}>
                    <PaperbaseContent/>
                </WebSocketContextProvider>
            </CameraProvider>
        </Provider>
    );
}

export default App;
