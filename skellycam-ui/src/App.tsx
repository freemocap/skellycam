import React, {useEffect} from 'react';
import {PaperbaseContent} from "@/layout/paperbase_theme/PaperbaseContent";
import {Provider} from "react-redux";
import {AppStateStore, useAppDispatch} from "@/store/AppStateStore";
import {LatestImagesContextProvider} from "@/context/latest-images-context/LatestImagesContext";
import {WebSocketContextProvider} from "@/context/websocket-context/WebSocketContext";
import {initializeWithExpandedPath} from "@/store/slices/recordingInfoSlice";


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
