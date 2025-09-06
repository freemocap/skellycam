import { createAsyncThunk } from '@reduxjs/toolkit';
import { setError, setIsLoading, setVideoFiles, setVideoFolder } from '../slices/videoLoadingSlice';
import { electronIpcClient } from '@/hooks/electron-service/electron-ipc-client';

interface FolderEntry {
    name: string;
    path: string;
    isDirectory: boolean;
    isFile: boolean;
    size: number;
    modified: string | number | Date;
}

const VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm'];

export const selectVideoFolder = createAsyncThunk(
    'videoLoading/selectFolder',
    async (_, { dispatch }) => {
        try {
            dispatch(setIsLoading(true));
            dispatch(setError(null));

            const selectedFolder = await electronIpcClient.fileSystem.selectDirectory.mutate();
            if (!selectedFolder) return null;

            dispatch(setVideoFolder(selectedFolder));
            const entries: FolderEntry[] = await electronIpcClient.fileSystem.getFolderContents.query({ path: selectedFolder });

            const videoFiles = (entries ?? [])
                .filter((item: FolderEntry) => item.isFile && VIDEO_EXTENSIONS.some(ext => item.name.toLowerCase().endsWith(ext)))
                .map((file: FolderEntry) => ({ name: file.name, path: file.path }));

            dispatch(setVideoFiles(videoFiles));
            return { folder: selectedFolder, files: videoFiles };
        } catch (error) {
            dispatch(setError(error instanceof Error ? error.message : 'Unknown error'));
            throw error;
        } finally {
            dispatch(setIsLoading(false));
        }
    }
);

export const loadVideos = createAsyncThunk(
    'videoLoading/loadVideos',
    async ({ folder, files }: { folder: string; files: { name: string; path: string }[] }, { dispatch }) => {
        try {
            dispatch(setIsLoading(true));
            dispatch(setError(null));
            const success = await electronIpcClient.fileSystem.openFolder.mutate({ path: folder });
            if (!success) throw new Error('Failed to open folder');
            return { success: true };
        } catch (error) {
            dispatch(setError(error instanceof Error ? error.message : 'Unknown error'));
            throw error;
        } finally {
            dispatch(setIsLoading(false));
        }
    }
);

export const openVideoFile = createAsyncThunk(
    'videoLoading/openVideoFile',
    async (filePath: string) => {
        try {
            const idx = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'));
            const folderPath = idx >= 0 ? filePath.substring(0, idx) : filePath;
            await electronIpcClient.fileSystem.openFolder.mutate({ path: folderPath });
            return { success: true };
        } catch (error) {
            console.error('Failed to open video file:', error);
            return { success: false, error };
        }
    }
);
