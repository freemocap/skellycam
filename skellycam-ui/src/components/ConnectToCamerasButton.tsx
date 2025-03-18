import React from 'react';
import {Button} from '@mui/material';
import axios from 'axios';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";

export const ConnectToCamerasButton = () => {
    const sendConnectDetectRequest = async () => {
        try {

            const response = await axios.post(`http://localhost:8006/skellycam/cameras/connect`,{
                camera_ids: [0]
            });

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
        <Button
            variant="contained"
            onClick={sendConnectDetectRequest}
            sx={{
                fontSize: '1.25rem',
                color: extendedPaperbaseTheme.palette.primary.contrastText,
                backgroundColor: extendedPaperbaseTheme.palette.primary.light,
            }}
        >
            Detect/Connect to Cameras
        </Button>
    );
};
