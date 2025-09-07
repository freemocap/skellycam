import { createAsyncThunk } from '@reduxjs/toolkit';
import {electronAPI} from "@/hooks/electron-service/electron-api";
import {VideoFile} from "@/store";

const VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm'];

interface FolderEntry {
    name: string;
    path: string;
    isDirectory: boolean;
    isFile: boolean;
    size: number;
    modified: string | number | Date;
}

export const selectVideoLoadFolder = createAsyncThunk<
    { folder: string; files: VideoFile[] } | null
>('videos/selectFolder', async () => {
    if (!electronAPI) {
        throw new Error('Electron API not available');
    }

    const selectedFolder = await electronAPI.fileSystem.selectDirectory.mutate();
    if (!selectedFolder) return null;

    const entries: FolderEntry[] = await electronAPI.fileSystem.getFolderContents.query({
        path: selectedFolder,
    });

    const videoFiles = (entries ?? [])
        .filter(
            (item) =>
                item.isFile &&
                VIDEO_EXTENSIONS.some((ext) => item.name.toLowerCase().endsWith(ext))
        )
        .map((file) => ({
            name: file.name,
            path: file.path,
            size: file.size,
        }));

    return { folder: selectedFolder, files: videoFiles };
});

export const loadVideos = createAsyncThunk<
    { success: boolean },
    { folder: string; files: VideoFile[] }
>('videos/load', async ({ folder }) => {
    if (!electronAPI) {
        throw new Error('Electron API not available');
    }

    const success = await electronAPI.fileSystem.openFolder.mutate({ path: folder });
    if (!success) {
        throw new Error('Failed to open folder');
    }
    return { success: true };
});

export const openVideoFile = createAsyncThunk<
    { success: boolean; error?: Error },
    string
>('videos/openFile', async (filePath) => {
    if (!electronAPI) {
        return { success: false, error: new Error('Electron API not available') };
    }

    try {
        const idx = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'));
        const folderPath = idx >= 0 ? filePath.substring(0, idx) : filePath;
        await electronAPI.fileSystem.openFolder.mutate({ path: folderPath });
        return { success: true };
    } catch (error) {
        console.error('Failed to open video file:', error);
        return {
            success: false,
            error: error instanceof Error ? error : new Error('Unknown error'),
        };
    }
});
