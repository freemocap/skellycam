import React from 'react';
import {Box, Button } from '@mui/material';
import axios from 'axios';

export const ConnectToCamerasButton = () => {
    const handleDetectCameras = async () => {
        try {
            const response = await axios.get(`${window.location.origin}/skellycam/cameras/connect/detect`);
            console.log('Response:', response.data);
        } catch (error) {
            console.error('Error detecting cameras:', error);
        }
    };

    return (
        <Box sx={{ margin: '1rem' }}>
        <Button
            variant="contained"
            onClick={handleDetectCameras}
            sx={ {fontSize: '1.25rem'
            }}
        >
            Detect/Connect to Cameras
        </Button>
        </Box>
    );
};
