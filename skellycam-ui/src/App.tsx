import React from 'react';
import {Paperbase} from "@/layout/paperbase_theme/Paperbase";
import {WebSocketProvider} from "@/context/WebSocketContext";


function App() {
    const _port = 8006;
    const wsUrl = `ws://localhost:${_port}/skellycam/websocket/connect`;
    return (
        <WebSocketProvider url={wsUrl}>
            <React.Fragment>
                <Paperbase/>
            </React.Fragment>
        </WebSocketProvider>
    );
}

export default App;
