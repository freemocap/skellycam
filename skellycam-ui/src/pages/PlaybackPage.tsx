import React, { useCallback, useEffect, useState } from 'react';
import { Footer } from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { RecordingBrowser, LoadedVideo } from '@/components/playback/RecordingBrowser';
import { SyncedVideoPlayer } from '@/components/playback/SyncedVideoPlayer';
import { CamerasViewSettingsOverlay } from '@/components/camera-view-settings-overlay/CamerasViewSettingsOverlay';
import { useElectronIPC } from '@/services';
import { serverUrls } from '@/services/server/server-helpers/server-urls';
import { backendFetch } from '@/services/electron-ipc/backend-fetch';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import IconButton from '@/components/ui-components/iconButton';

// Module-level cache so playback state survives tab switches
let cachedPlaybackState: {
    loadedVideos: LoadedVideo[];
    recordingId: string | null;
    recordingPath: string | null;
    recordingFps: number | undefined;
    frameTimestamps: Record<string, number[]> | null;
    currentFrame: number;
} = {
    loadedVideos: [],
    recordingId: null,
    recordingPath: null,
    recordingFps: undefined,
    frameTimestamps: null,
    currentFrame: 0,
};

const PlaybackPage: React.FC = () => {
    const { t } = useTranslation();
    const { api } = useElectronIPC();
    const location = useLocation();
    const locationState = location.state as { loadRecordingPath?: string } | null;
    const initialLoadPath = locationState?.loadRecordingPath ?? null;

    // If navigating here with a new recording path, clear cached state so RecordingBrowser shows and auto-loads
    const initState = (initialLoadPath && initialLoadPath !== cachedPlaybackState.recordingPath)
        ? { loadedVideos: [] as LoadedVideo[], recordingId: null, recordingPath: null, recordingFps: undefined, frameTimestamps: null, currentFrame: 0 }
        : cachedPlaybackState;

    const [loadedVideos, setLoadedVideos] = useState<LoadedVideo[]>(initState.loadedVideos);
    const [recordingId, setRecordingId] = useState<string | null>(initState.recordingId);
    const [recordingPath, setRecordingPath] = useState<string | null>(initState.recordingPath);
    const [recordingFps, setRecordingFps] = useState<number | undefined>(initState.recordingFps);
    const [frameTimestamps, setFrameTimestamps] = useState<Record<string, number[]> | null>(initState.frameTimestamps);
    const [manualColumns, setManualColumns] = useState<number | null>(null);
    const [resetKey, setResetKey] = useState<number>(0);

    const handleRecordingLoaded = useCallback((videos: LoadedVideo[], recId: string, path: string, fps?: number) => {
        setLoadedVideos(videos);
        setRecordingId(recId);
        setRecordingPath(path);
        setRecordingFps(fps);
        setFrameTimestamps(null);
        cachedPlaybackState = { loadedVideos: videos, recordingId: recId, recordingPath: path, recordingFps: fps, frameTimestamps: null, currentFrame: 0 };
    }, []);

    // After a recording is loaded, fetch real timestamps from the server
    useEffect(() => {
        if (loadedVideos.length === 0 || !recordingId) return;

        const fetchTimestamps = async () => {
            try {
                const response = await backendFetch(serverUrls.endpoints.playbackAllTimestamps(recordingId));
                if (!response.ok) return;
                const data = await response.json();
                if (data.timestamps && Object.keys(data.timestamps).length > 0) {
                    setFrameTimestamps(data.timestamps);
                    cachedPlaybackState.frameTimestamps = data.timestamps;
                }
            } catch {
                // Timestamps not available — SyncedVideoPlayer will use approximation
            }
        };
        fetchTimestamps();
    }, [loadedVideos, recordingId]);

    const handleBack = useCallback(() => {
        setLoadedVideos([]);
        setRecordingId(null);
        setRecordingPath(null);
        setRecordingFps(undefined);
        setFrameTimestamps(null);
        cachedPlaybackState = { loadedVideos: [], recordingId: null, recordingPath: null, recordingFps: undefined, frameTimestamps: null, currentFrame: 0 };
    }, []);

    const handleOpenFolder = useCallback(async () => {
        if (!recordingPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({ path: recordingPath });
        } catch (err) {
            console.error('Failed to open recording folder:', err);
            throw err;
        }
    }, [recordingPath, api]);

    const handleSettingsChange = useCallback((settings: { columns: number | null }) => {
        setManualColumns(settings.columns);
    }, []);

    const handleResetLayout = useCallback(() => {
        setResetKey((v) => v + 1);
    }, []);

    const handleFrameChange = useCallback((frame: number) => {
        cachedPlaybackState.currentFrame = frame;
    }, []);

    const hasVideos = loadedVideos.length > 0;
    const totalSize = loadedVideos.reduce((sum, v) => sum + v.sizeBytes, 0);

    const recordingName = recordingPath ? recordingPath.split(/[\\/]/).pop() || recordingPath : '';

    return (
        <div className="playback-page h-full flex flex-col" style={{ borderLeft: '1px solid var(--gray-700)' }}>
            <div className='mode-header playback-mode w-full reveal fadeIn active-tools-header br-1-1 gap-1 p-1 flex justify-content-space-between'>
                
            </div><div className="playback-page-content-main flex flex-col flex-1 overflow-hidden p-2 bg-middark rounded mt-1 br-2">
                <ErrorBoundary>
                    {hasVideos ? (
                        <div className="playback-page-content no-videos empty-state flex flex-col h-full">
                            {/* Recording header bar */}
                            <div
                                className="playack-page-with-video flex items-center gap-2 px-2 py-1 flex-wrap m-1 ml-2"
                                
                                        >   
                                        <IconButton
                                            icon="back-icon"
                                            onClick={handleBack}
                                            tooltip="yes"
                                            tooltipText='Back'
                                            tooltipPosition='pos-bottom'
                                            />
                              
                                    
                               

                                <p className="text sm recording-name flex-1 overflow-hidden" style={{ textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
                                    {recordingName}
                                </p>

                                <button
                                    className="button md"
                                    onClick={handleOpenFolder}
                                    title={t('openFolder')}
                                >
                                    <span className="icon import-icon icon-size-20" />
                                </button>

                                <span className="camera-config-chip" title={t('cameraStreams')}>
                                    {t('cameraCount', { count: loadedVideos.length })}
                                </span>

                                {totalSize > 0 && (
                                    <span className="camera-config-chip" title={t('totalRecordingSize')}>
                                        {formatBytes(totalSize)}
                                    </span>
                                )}

                                {recordingFps != null && recordingFps > 0 && (
                                    <span className="camera-config-chip" title={t('recordingCaptureFps')}>
                                        rec: {recordingFps} fps
                                    </span>
                                )}

                                <CamerasViewSettingsOverlay
                                    inline
                                    onSettingsChange={handleSettingsChange}
                                    onResetLayout={handleResetLayout}
                                />
                            </div>

                            {/* Player */}
                            <div className="flex-1" style={{ minHeight: 0 }}>
                                <SyncedVideoPlayer
                                    videos={loadedVideos.map((v) => ({
                                        videoId: v.videoId,
                                        filename: v.filename,
                                        streamUrl: v.streamUrl,
                                    }))}
                                    recordingFps={recordingFps}
                                    frameTimestamps={frameTimestamps}
                                    manualColumns={manualColumns}
                                    resetKey={resetKey}
                                    initialFrame={initState.currentFrame}
                                    onFrameChange={handleFrameChange}
                                />
                            </div>
                        </div>
                    ) : (
                        <RecordingBrowser onRecordingLoaded={handleRecordingLoaded} initialLoadPath={initialLoadPath} />
                    )}
                </ErrorBoundary>
            </div>

            <footer className="p-1">
                <Footer />
            </footer>
        </div>
    );
};

function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
}

export default PlaybackPage;
