import React from 'react';
import {Route, Routes} from "react-router-dom";
import {ConfigView} from "@/views/Config";
import {CamerasView} from "@/views/CamerasView";
import WebsocketConnectionStatus from "@/components/ui-components/WebsocketConnectionStatus";
import {WelcomeView} from "@/views/WelcomeView/WelcomeView";

export const Router = () => {
    return (
        <Routes>
            <Route path={'/'} element={<WelcomeView />} />
            <Route path={'/cameras'} element={<CamerasView />} />
            <Route path={'/config'} element={<ConfigView/>}/>
            <Route path={'/websocketConnection'} element={<WebsocketConnectionStatus/>}/>
        </Routes>
    )
}
