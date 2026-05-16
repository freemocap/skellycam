import React, { useEffect, useCallback, useState } from 'react';
import clsx from 'clsx';
import { useAppDispatch, useAppSelector, selectCameras, selectConnectedCameras, selectIsLoading, detectCameras } from '@/store';
import { camerasConnectOrUpdate, pauseUnpauseCameras, closeCameras } from '@/store/slices/cameras/cameras-thunks';
import { savedSettingsCleared } from '@/store/slices/cameras/cameras-slice';
import { selectIsPaused } from '@/store/slices/cameras/cameras-selectors';
import { CameraTreeItem } from './CameraTreeItem';
import { NoCamerasPlaceholder } from './NoCamerasPlaceholder';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';
import ButtonSm from '@/components/ui-components/ButtonSm';
import IconButton from "@/components/ui-components/IconButton";
import PromptTooltip from '@/components/ui-components/promptTooltip';


export const CameraConfigSidebarPanel: React.FC = () => {
    const [isStoppingCameras, setIsStoppingCameras] = useState(false);
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

    useEffect(() => {
        if (isStoppingCameras && connectedCameras.length === 0) {
            setIsStoppingCameras(false);
        }
    }, [isStoppingCameras, connectedCameras.length]);

    const handleUpdate = useCallback(() => {
        dispatch(camerasConnectOrUpdate());
    }, [dispatch]);

    const handleDetect = useCallback(() => {
        dispatch(detectCameras({ filterVirtual: true }));
    }, [dispatch]);

    const handleStop = useCallback(() => {
        setIsStoppingCameras(true);
        dispatch(closeCameras());
    }, [dispatch]);

    return (
        <div className="camera-config-sidebar-panel flex flex-col flex-1 bg-middark br-2 p-1 min-h-0">
            {/* Header */}
            <div className="camera-group-header flex flex-col gap-1 p-1 pos-rel z-2">
                {/* Row 1 — actions */}
              
                <div className="flex items-center gap-1 overflow-visible">
                    
                     <PromptTooltip
  show={true}

title="Connect Cameras"

text="Make sure you have at least one camera connected, then hit Connect to start streaming."
  position="pos-bottom"
  variant="boarding"

  onClose={() => {
    console.log("Tooltip closed");
  }}
/>
                    <p className="text md text-gray">{cameras.length} Cameras</p>
{connectedCameras.length > 0 && (
    <span
        className="text md"
        style={{ color: 'var(--green-400, #4ade80)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
    >
        {/* <span className="icon icon-size-20 streaming-icon" /> */}
        {connectedCameras.length} Streaming
    </span>
)}
                    <div className="flex-1" />
                    {/* Buttons: Detect + Connect OR Pause/Stop (when connected) */}
                    <div className="button-group flex items-center gap-1 pos-rel">
                           
                           
                        
                     
                     <IconButton
                        icon="scan-icon"
                        onClick={handleDetect}
                        tooltip={true}
                        tooltipText="Detect new cameras"
                        tooltipPosition="pos-bottom"
                    />
                        {connectedCameras.length === 0 ? (
                            <ButtonSm
                              text={isLoading ? 'Connecting...' : 'Connect Cameras'}
                              iconClass={isLoading ? 'loader-icon' : 'stream-icon'}
                              onClick={handleUpdate}
                              textColor = "text-black"
                              className="secondary"
                            tooltip={true}
                            tooltipText="Connect to Cameras"
                            tooltipPosition="pos-bottom"

                            />
                        ) : (
                            <>
                                <button
                                    className="button icon-button"
                                    onClick={() => dispatch(pauseUnpauseCameras())}
                                    title={isPaused ? t('resumeStreaming') : t('pauseStreaming')}
                                >
                                    <span className={clsx('icon icon-size-20', isPaused ? 'play-icon' : 'pause-icon')} />
                                </button>
                                <button className="button icon-button" onClick={handleStop} title="Stop streaming" disabled={isStoppingCameras}>
                                    <span className={`icon icon-size-20 ${isStoppingCameras ? 'loader-icon' : 'stopstreaming-icon'}`} />
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </div>

            {/* Camera list */}
            <div className="camera-list-container flex flex-col overflow-y z-1 pos-rel">
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
