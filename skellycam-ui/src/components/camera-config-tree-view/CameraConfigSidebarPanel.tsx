import React, { useEffect, useCallback } from 'react';
import { useAppDispatch, useAppSelector, selectCameras, selectConnectedCameras, selectIsLoading, detectCameras } from '@/store';
import { camerasConnectOrUpdate } from '@/store/slices/cameras/cameras-thunks';
import { savedSettingsCleared } from '@/store/slices/cameras/cameras-slice';
import { CameraTreeItem } from './CameraTreeItem';
import { NoCamerasPlaceholder } from './NoCamerasPlaceholder';
import { useServer } from '@/services/server/ServerContextProvider';

export const CameraConfigSidebarPanel: React.FC = () => {
    const dispatch = useAppDispatch();
    const { isConnected } = useServer();
    const cameras = useAppSelector(selectCameras);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const isLoading = useAppSelector(selectIsLoading);

    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [isConnected, cameras.length, dispatch]);

    const handleUpdate = useCallback(() => {
        dispatch(camerasConnectOrUpdate());
    }, [dispatch]);

    const handleDetect = useCallback(() => {
        dispatch(detectCameras({ filterVirtual: true }));
    }, [dispatch]);

    return (
        <div className="flex flex-col flex-1 overflow-hidden bg-dark br-2 border-1 border-black p-1 m-1">
            {/* Header */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '4px', borderBottom: '1px solid var(--gray-700)' }}>
                {/* Row 1 — actions */}
                <div className="flex items-center gap-1">
                    <p className="text bg text-white">{cameras.length} Cameras</p>
                    <button className="button icon-button" onClick={handleDetect} title="Detect cameras">
                        <span className={`icon icon-size-16 ${isLoading ? 'loader-icon' : 'scan-icon'}`} />
                    </button>
                    <div className="flex-1" />
                    <button className="button icon-button" onClick={() => dispatch(savedSettingsCleared())} title="Reset all cameras to default settings">
                        <span className="icon icon-size-16 clear-icon" />
                    </button>
                    <button className="button sm br-1" onClick={handleUpdate} style={{ background: 'var(--gray-100)', color: 'var(--gray-900)' }}>
                        <p className="text md" style={{ color: 'var(--gray-900)' }}>Update</p>
                    </button>
                </div>
                {/* Row 2 — streaming chip */}
                {connectedCameras.length > 0 && (
                    <div className="flex items-center gap-1">
                        <span className="tag" style={{ color: 'var(--green-400, #4ade80)' }}>
                            {connectedCameras.length} Streaming
                        </span>
                    </div>
                )}
            </div>

            {/* Camera list */}
            <div className="flex flex-col overflow-y-auto">
                {cameras.length === 0 ? (
                    <NoCamerasPlaceholder />
                ) : (
                    cameras
                        .slice()
                        .sort((a, b) => a.index - b.index)
                        .map(camera => (
                            <CameraTreeItem key={camera.id} camera={camera} />
                        ))
                )}
            </div>
        </div>
    );
};
