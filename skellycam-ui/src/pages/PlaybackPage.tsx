import React, { useCallback, useState } from 'react';
import { Box, Button, Typography, useTheme } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import { Footer } from '@/components/ui-components/Footer';
import { RecordingBrowser, LoadedVideo } from '@/components/playback/RecordingBrowser';
import { SyncedVideoPlayer } from '@/components/playback/SyncedVideoPlayer';

type PlaybackView = 'browser' | 'player';

const PlaybackPage: React.FC = () => {
    const theme = useTheme();
    const [view, setView] = useState<PlaybackView>('browser');
    const [loadedVideos, setLoadedVideos] = useState<LoadedVideo[]>([]);
    const [recordingPath, setRecordingPath] = useState<string>('');

    const handleRecordingLoaded = useCallback((videos: LoadedVideo[], path: string) => {
        setLoadedVideos(videos);
        setRecordingPath(path);
        setView('player');
    }, []);

    const handleBackToBrowser = useCallback(() => {
        setView('browser');
        setLoadedVideos([]);
        setRecordingPath('');
    }, []);

    return (
        <Box
            sx={{
                py: 1,
                px: 1,
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: theme.palette.divider,
            }}
        >
            <ErrorBoundary>
                {view === 'browser' ? (
                    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                        <Typography variant="h5" sx={{ px: 2, pt: 1, pb: 0.5 }}>
                            📹 Playback
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ px: 2, pb: 1 }}>
                            Select a recording to play back synchronized videos.
                        </Typography>
                        <Box sx={{ flex: 1, overflow: 'auto' }}>
                            <RecordingBrowser onRecordingLoaded={handleRecordingLoaded} />
                        </Box>
                    </Box>
                ) : (
                    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                        {/* Header bar with back button and recording name */}
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1, py: 0.5, borderBottom: `1px solid ${theme.palette.divider}` }}>
                            <Button
                                size="small"
                                startIcon={<ArrowBackIcon />}
                                onClick={handleBackToBrowser}
                            >
                                Back
                            </Button>
                            <Typography
                                variant="body2"
                                sx={{ fontFamily: 'monospace', color: theme.palette.text.secondary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            >
                                {recordingPath}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto', whiteSpace: 'nowrap' }}>
                                {loadedVideos.length} video{loadedVideos.length !== 1 ? 's' : ''}
                            </Typography>
                        </Box>

                        {/* Synced video player */}
                        <Box sx={{ flex: 1, minHeight: 0 }}>
                            <SyncedVideoPlayer
                                videos={loadedVideos.map((v) => ({
                                    videoId: v.videoId,
                                    filename: v.filename,
                                    streamUrl: v.streamUrl,
                                }))}
                            />
                        </Box>
                    </Box>
                )}
            </ErrorBoundary>

            <Box component="footer" sx={{ p: 1 }}>
                <Footer />
            </Box>
        </Box>
    );
};

export default PlaybackPage;
