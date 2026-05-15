import React, { useEffect, useCallback } from 'react';
import clsx from 'clsx';
import { useAppDispatch, useAppSelector, selectCameras, selectConnectedCameras, selectIsLoading, detectCameras } from '@/store';
import { camerasConnectOrUpdate, pauseUnpauseCameras } from '@/store/slices/cameras/cameras-thunks';
import { savedSettingsCleared } from '@/store/slices/cameras/cameras-slice';
import { selectIsPaused } from '@/store/slices/cameras/cameras-selectors';
import { CameraTreeItem } from './CameraTreeItem';
import { NoCamerasPlaceholder } from './NoCamerasPlaceholder';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';
import ButtonSm from '@/components/ui-components/ButtonSm';

export const CameraConfigSidebarPanel: React.FC = () => {
    const dispatch = useAppDispatch();
    const { isConnected } = useServer();
    const { t } = useTranslation();
    const cameras = useAppSelector(selectCameras);
    const connectedCameras = useAppSelector(selectConnectedCameras);
    const isLoading = useAppSelector(selectIsLoading);
    const isPaused = useAppSelector(selectIsPaused);

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
        <div className="camera-config-sidebar-panelflex flex-col flex-1 overflow-hidden bg-middark br-2 p-1">
            {/* Header */}
            <div className="camera-group-header flex flex-col gap-1 p-1">
                {/* Row 1 — actions */}
                <div className="text-nowrap flex items-center gap-1">
                    <p className="text md text-gray">{cameras.length} Cameras</p>
                    {connectedCameras.length > 0 && (
                        <span className="text md tag" style={{ color: 'var(--green-400, #4ade80)' }}>
                            {connectedCameras.length} Streaming
                        </span>
                    )}
                    <div className="flex-1" />
                    {/* Buttons: Detect + Connect OR Pause/Stop (when connected) */}
                    <div className="button-group text-nowrap flex items-center gap-1">
                        <button className="button icon-button" onClick={handleDetect} title="Detect cameras">
                            <span className={`icon icon-size-16 ${isLoading ? 'loader-icon' : 'scan-icon'}`} />
                        </button>
                        {connectedCameras.length === 0 ? (
                            <ButtonSm
                              text={isLoading ? 'Checking...' : 'Stream Cameras'}
                              iconClass="stream-icon"
                              onClick={handleUpdate}
                              className="br-1"
                            />
                        ) : (
                            <>
                                <button
                                    className="button icon-button"
                                    onClick={() => dispatch(pauseUnpauseCameras())}
                                    title={isPaused ? t('resumeStreaming') : t('pauseStreaming')}
                                >
                                    <span className={clsx('icon icon-size-16', isPaused ? 'play-icon' : 'pause-icon')} />
                                </button>
                                <button className="button icon-button" title="Stop streaming">
                                    <span className="icon icon-size-16 stop-streaming-icon" />
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </div>

            {/* Camera list */}
            <div className="camera-list-container flex flex-col overflow-y">
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
