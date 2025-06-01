import React from 'react';
import {IconButton} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import {useAppDispatch} from '@/store/AppStateStore';
import {closeCameras} from "@/store/thunks/close-cameras-thunks";


export const CloseCamerasButton: React.FC = () => {
    const dispatch = useAppDispatch();

    const handleCloseCameras = () => {
        dispatch(closeCameras());
    };

    return (
        <IconButton
            color="inherit"
            onClick={handleCloseCameras}

        >
            <CloseIcon/>
        </IconButton>
    );
};
