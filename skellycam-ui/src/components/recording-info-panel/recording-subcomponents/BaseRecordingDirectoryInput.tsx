import React from 'react';
import {IconButton, InputAdornment, TextField} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import {useAppDispatch} from "@/store/AppStateStore";
import {setRecordingInfo} from "@/store/slices/recordingInfoSlice";
import {useElectronAPI} from "@/hooks/electron-service/useElectronApi";

interface DirectoryInputProps {
    value: string;
}

export const BaseRecordingDirectoryInput: React.FC<DirectoryInputProps> = ({value}) => {
    const dispatch = useAppDispatch();
    const { fileSystem } = useElectronAPI();

    const handleSelectDirectory = async () => {
        try {
            const result = await fileSystem?.selectDirectory();
            if (result) {
                dispatch(setRecordingInfo({recordingDirectory: result}));
            }
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };

    const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const newPath = e.target.value;
        if (newPath.includes('~')) {
            try {
                const home = await fileSystem?.getHomeDirectory();
                const expanded = home ? newPath.replace(/^~(\/|\\)?/, `${home}$1` || home) : newPath;
                dispatch(setRecordingInfo({ recordingDirectory: expanded }));
            } catch {
                dispatch(setRecordingInfo({ recordingDirectory: newPath }));
            }
        } else {
            dispatch(setRecordingInfo({ recordingDirectory: newPath }));
        }
    };

    return (
        <TextField
            label="Recording Directory"
            value={value}
            onChange={handleInputChange}
            fullWidth
            size="small"
            InputProps={{
                endAdornment: (
                    <InputAdornment position="end">
                        <IconButton onClick={handleSelectDirectory} edge="end">
                            <FolderOpenIcon/>
                        </IconButton>
                    </InputAdornment>
                ),
            }}
        />
    );
};
