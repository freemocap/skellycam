import * as React from 'react';
import {useState} from "react";
import clsx from "clsx";
import {useLocation, useNavigate} from "react-router-dom";
import {useTranslation} from "react-i18next";
import {useAppDispatch, useAppSelector} from "@/store";
import {startRecording, stopRecording} from "@/store";
import {useServer} from "@/services/server/ServerContextProvider";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";
import {CameraConfigTreeView} from "@/components/camera-config-tree-view/CameraConfigTreeView";
import {getTimestampString} from "@/components/recording-info-panel/getTimestampString";

interface LeftSidePanelContentProps {
    isCollapsed: boolean;
    onToggleCollapse: () => void;
}

const CollapsedToolbar: React.FC<{
    onToggleCollapse: () => void;
    isRecording: boolean;
    noCameras: boolean;
    onRecordClick: () => void;
}> = ({onToggleCollapse, isRecording, noCameras, onRecordClick}) => {
    const {t} = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();

    return (
        <div className="flex flex-col items-center w-full h-full pt-1 gap-1" style={{backgroundColor: 'var(--gray-800)'}}>
            <button
                className="button icon-button"
                onClick={onToggleCollapse}
                title={t('expandSidebar')}
            >
                <span className="text sm">☰</span>
            </button>

            <button
                className={clsx("button icon-button record-button-sm", isRecording ? "record-button-active" : "record-button-idle")}
                onClick={onRecordClick}
                disabled={noCameras && !isRecording}
                title={isRecording ? t('stopRecording') : t('startRecording')}
            >
                <span className={clsx("icon icon-size-16", isRecording ? "close-icon" : "record-icon")} />
            </button>

            <button
                className="button icon-button"
                onClick={() => navigate('/cameras')}
                title={t('cameras')}
                style={{color: location.pathname === '/cameras' ? 'var(--green-100)' : undefined}}
            >
                <span className="icon stream-icon icon-size-16" />
            </button>

            <button
                className="button icon-button"
                onClick={() => navigate('/playback')}
                title={t('videoPlayback')}
                style={{color: location.pathname === '/playback' ? 'var(--blue-100)' : undefined}}
            >
                <span className="icon video-icon icon-size-16" />
            </button>
        </div>
    );
};

export const LeftSidePanelContent: React.FC<LeftSidePanelContentProps> = ({isCollapsed, onToggleCollapse}) => {
    const navigate = useNavigate();
    const location = useLocation();
    const dispatch = useAppDispatch();
    const {t} = useTranslation();

    const recordingInfo = useAppSelector((state) => state.recording);
    const isRecording = recordingInfo.isRecording;
    const {connectedCameraIds} = useServer();
    const noCameras = connectedCameraIds.length === 0;
    const [micDeviceIndex] = useState<number>(-1);

    const handleCollapsedRecordClick = async (): Promise<void> => {
        if (isRecording) {
            await dispatch(stopRecording()).unwrap();
        } else {
            const recordingName = getTimestampString();
            await dispatch(startRecording({
                recordingName,
                recordingDirectory: recordingInfo.recordingDirectory,
                micDeviceIndex,
            })).unwrap();
        }
    };

    if (isCollapsed) {
        return (
            <CollapsedToolbar
                onToggleCollapse={onToggleCollapse}
                isRecording={isRecording}
                noCameras={noCameras}
                onRecordClick={handleCollapsedRecordClick}
            />
        );
    }

    return (
        <div
            className="flex flex-col w-full h-full overflow-y-auto overflow-x-hidden"
            style={{backgroundColor: 'var(--gray-800)'}}
        >
            {/* Header row */}
            <div
                className="flex items-center gap-1 px-1 py-1"
                style={{
                    borderBottom: '1px solid var(--gray-600)',
                    minHeight: 40,
                }}
            >
                <button
                    className="button icon-button"
                    onClick={onToggleCollapse}
                    title={t('collapseSidebar')}
                >
                    <span className="text sm">✕</span>
                </button>

                <span
                    className="text bg flex-1 overflow-hidden"
                    style={{textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0}}
                >
                    SkellyCam 💀📸
                </span>
            </div>

            {/* Cameras / Playback nav tabs */}
            <div className="flex gap-1 px-1 py-1" style={{borderBottom: '1px solid var(--gray-600)'}}>
                <button
                    className={clsx("button sm flex-1 justify-center", location.pathname === '/cameras' ? "sidebar-nav-cameras" : "sidebar-nav-inactive")}
                    onClick={() => navigate('/cameras')}
                >
                    <span className="icon stream-icon icon-size-16" />
                    <span className="text sm">{t('cameras')}</span>
                </button>
                <button
                    className={clsx("button sm flex-1 justify-center", location.pathname === '/playback' ? "sidebar-nav-playback" : "sidebar-nav-inactive")}
                    onClick={() => navigate('/playback')}
                >
                    <span className="icon video-icon icon-size-16" />
                    <span className="text sm">{t('videoPlayback')}</span>
                </button>
            </div>

            {/* Main content */}
            <div className="flex flex-col gap-1 pt-1 pb-4">
                <RecordingInfoPanel/>
                <CameraConfigTreeView/>
            </div>
        </div>
    );
};
