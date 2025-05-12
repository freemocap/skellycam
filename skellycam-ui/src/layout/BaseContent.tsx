// skellycam-ui/src/layout/BaseContent.tsx
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import WelcomePage from "@/layout/pages/WelcomePage";
import {CamerasPage} from "@/layout/pages/CamerasPage";
import LoadVideosPage from "@/layout/pages/VideosPage";

export const BaseRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/" element={<WelcomePage />} />
            <Route path="/cameras" element={<CamerasPage />} />
            <Route path="/videos" element={<LoadVideosPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
};
