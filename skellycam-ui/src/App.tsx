import React from 'react';
import {PaperbaseContent} from "@/layout/base-content/paperbase_theme/PaperbaseContent";
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
                    <PaperbaseContent/>
                </React.Fragment>
            </WebSocketContextProvider>
        </Provider>
    );
}

export default App;
