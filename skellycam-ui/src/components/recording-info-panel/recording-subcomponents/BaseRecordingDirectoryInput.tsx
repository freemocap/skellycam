import React from 'react';
import {IconButton, InputAdornment, TextField} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import {useAppDispatch} from "@/store/AppStateStore";
import {setRecordingInfo} from "@/store/slices/recordingInfoSlice";

interface DirectoryInputProps {
    value: string;
}

export const BaseRecordingDirectoryInput: React.FC<DirectoryInputProps> = ({value}) => {
    const dispatch = useAppDispatch();

    const handleSelectDirectory = async () => {
        try {
            const result = await window.electronAPI.selectDirectory();
            if (result) {
                dispatch(setRecordingInfo({recordingDirectory: result}));
            }
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };

    return (
        <TextField
            label="Recording Directory"
            value={value}
            onChange={(e) => dispatch(setRecordingInfo({recordingDirectory: e.target.value}))}
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
