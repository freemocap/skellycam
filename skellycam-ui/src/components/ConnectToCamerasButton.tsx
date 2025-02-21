import React from 'react';
import {Box, Button} from '@mui/material';
import axios from 'axios';

export const ConnectToCamerasButton = () => {
    const sendConnectDetectRequest = async () => {
        try {

            const response = await axios.get(`http://localhost:8006/skellycam/cameras/connect/detect`);

            if (response.status === 200) {
                console.log('Cameras detect/connect request sent successfully');

            } else {
                console.error(`Error sending cameras detect/connect request: ${response.status}`);
            }
        } catch (error) {
            console.error('Error detecting cameras:', error);
        }
    };

    return (
        <Box sx={{margin: '1rem'}}>
            <Button
                variant="contained"
                onClick={sendConnectDetectRequest}
                sx={{
                    fontSize: '1.25rem'
                }}
            >
                Detect/Connect to Cameras
            </Button>
        </Box>
    );
};
