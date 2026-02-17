import React, { useCallback, useEffect, useState } from 'react';
import {
    Box,
    Button,
    CircularProgress,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    TextField,
    Typography,
    useTheme,
} from '@mui/material';
import FolderIcon from '@mui/icons-material/Folder';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import { serverUrls } from '@/services/server/server-helpers/server-urls';

interface RecordingEntry {
    name: string;
    path: string;
    video_count: number;
}

export interface LoadedVideo {
    videoId: string;
    filename: string;
    streamUrl: string;
    sizeBytes: number;
}

interface RecordingBrowserProps {
    onRecordingLoaded: (videos: LoadedVideo[], recordingPath: string) => void;
}

export const RecordingBrowser: React.FC<RecordingBrowserProps> = ({ onRecordingLoaded }) => {
    const theme = useTheme();
    const [recordings, setRecordings] = useState<RecordingEntry[]>([]);
    const [isLoadingList, setIsLoadingList] = useState(false);
    const [isLoadingRecording, setIsLoadingRecording] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [manualPath, setManualPath] = useState('');

    const fetchRecordings = useCallback(async () => {
        setIsLoadingList(true);
        setError(null);
        try {
            const response = await fetch(serverUrls.endpoints.playbackRecordings);
            if (!response.ok) {
                throw new Error(`Failed to fetch recordings: ${response.statusText}`);
            }
            const data: RecordingEntry[] = await response.json();
            setRecordings(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to fetch recordings');
        } finally {
            setIsLoadingList(false);
        }
    }, []);

    useEffect(() => {
        fetchRecordings();
    }, [fetchRecordings]);

    const loadRecording = useCallback(async (recordingPath: string) => {
        setIsLoadingRecording(true);
        setError(null);
        try {
            const response = await fetch(serverUrls.endpoints.playbackLoad, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ recording_path: recordingPath }),
            });
            if (!response.ok) {
                const detail = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(detail.detail || response.statusText);
            }
            const data = await response.json();
            const baseUrl = serverUrls.getHttpUrl();
            const videos: LoadedVideo[] = data.videos.map((v: { video_id: string; filename: string; stream_url: string; size_bytes: number }) => ({
                videoId: v.video_id,
                filename: v.filename,
                streamUrl: `${baseUrl}${v.stream_url}`,
                sizeBytes: v.size_bytes,
            }));
            onRecordingLoaded(videos, data.recording_path);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load recording');
        } finally {
            setIsLoadingRecording(false);
        }
    }, [onRecordingLoaded]);

    const handleLoadManualPath = useCallback(() => {
        if (manualPath.trim()) {
            loadRecording(manualPath.trim());
        }
    }, [manualPath, loadRecording]);

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 2, height: '100%' }}>
            {/* Manual path input */}
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <TextField
                    fullWidth
                    size="small"
                    label="Recording folder path"
                    placeholder="~/skellycam_data/recordings/2024-01-01..."
                    value={manualPath}
                    onChange={(e) => setManualPath(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleLoadManualPath(); }}
                    disabled={isLoadingRecording}
                />
                <Button
                    variant="contained"
                    onClick={handleLoadManualPath}
                    disabled={!manualPath.trim() || isLoadingRecording}
                    startIcon={isLoadingRecording ? <CircularProgress size={16} /> : <PlayArrowIcon />}
                    sx={{ whiteSpace: 'nowrap' }}
                >
                    Load
                </Button>
            </Box>

            {error && (
                <Typography color="error" variant="body2">{error}</Typography>
            )}

            {/* Recordings list */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="subtitle2" color="text.secondary">
                    Available Recordings
                </Typography>
                <Button size="small" startIcon={<RefreshIcon />} onClick={fetchRecordings} disabled={isLoadingList}>
                    Refresh
                </Button>
            </Box>

            {isLoadingList ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                </Box>
            ) : recordings.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    No recordings found in default directory.
                    Enter a path above to load a recording manually.
                </Typography>
            ) : (
                <List
                    dense
                    sx={{
                        flex: 1,
                        overflow: 'auto',
                        border: `1px solid ${theme.palette.divider}`,
                        borderRadius: 1,
                    }}
                >
                    {recordings.map((rec) => (
                        <ListItemButton
                            key={rec.path}
                            onClick={() => loadRecording(rec.path)}
                            disabled={isLoadingRecording}
                        >
                            <ListItemIcon sx={{ minWidth: 36 }}>
                                <FolderIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText
                                primary={rec.name}
                                secondary={`${rec.video_count} video${rec.video_count !== 1 ? 's' : ''}`}
                                primaryTypographyProps={{ variant: 'body2', fontFamily: 'monospace' }}
                            />
                        </ListItemButton>
                    ))}
                </List>
            )}
        </Box>
    );
};
