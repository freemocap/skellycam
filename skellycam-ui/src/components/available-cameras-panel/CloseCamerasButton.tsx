import React from 'react';
import {IconButton, Tooltip} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import {useAppDispatch} from '@/store';
import {closeCameras} from "@/store/slices/cameras/old-camera-thunks/close-cameras-thunks";


export const CloseCamerasButton: React.FC = () => {
    const dispatch = useAppDispatch();

    const handleCloseCameras = () => {
        dispatch(closeCameras());
    };

    return (
        <Tooltip title="Close all cameras" arrow placement="bottom">
            <IconButton
                color="inherit"
                onClick={handleCloseCameras}
            >
                <CloseIcon/>
            </IconButton>
        </Tooltip>
    );
};
