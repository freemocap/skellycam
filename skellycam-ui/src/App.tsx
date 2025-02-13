import React from 'react';
import {Paperbase} from "@/layout/paperbase_theme/Paperbase";
import {WebSocketContextProvider} from "@/context/WebSocketContext";
import {Provider} from "react-redux";
import {AppStateStore} from "@/store/appStateStore";


function App() {
    const _port = 8006;
    const wsUrl = `ws://localhost:${_port}/skellycam/websocket/connect`;
    return (
        <Provider store={AppStateStore}>
            <WebSocketContextProvider url={wsUrl}>
                <React.Fragment>
                    <Paperbase/>
                </React.Fragment>
            </WebSocketContextProvider>
        </Provider>
    );
}

export default App;
