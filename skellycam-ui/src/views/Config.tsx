import {Box, Typography} from "@mui/material";
import React from "react";
import {useAsync} from "react-use";
import {DetectAvailableCameraDevices} from "@/services/detectCameraDevices";
import {useWebSocketContext} from "@/context/WebSocketContext";
import {useSelector} from "react-redux";
import {RootState} from "@/store/appStateStore";

export const ConfigView = () => {
    const [devices, setDevices] = React.useState<MediaDeviceInfo[]>([]);
    const { latestSkellyCamAppState } = useWebSocketContext();
    const availableCameras = useSelector((state: RootState) => state.availableCameras.available_cameras);


    useAsync(async () => {
        const cam = new DetectAvailableCameraDevices();
        const deviceInfos = await cam.findAllCameras(false);
        setDevices(deviceInfos);
    }, []); // Adding an empty dependency array to ensure this runs once on component mount

    const devicesWithNames = devices.filter(x => x.label);


    return (
        <Box>
            <h2 style={{ color: 'white' }}>JS Detected Cameras</h2>
            {devicesWithNames.map(device => (
                <Typography key={device.deviceId} style={{ color: '#fafafa' }}>
                    Webcam {device.label}
                </Typography>
            ))}
            <br/>
            <h2 style={{ color: '#fafafa' }}>Latest SkellyCamAppState</h2>
            {latestSkellyCamAppState && (
                <Typography component="pre" style={{ color: '#fafafa' }}>
                    {JSON.stringify(latestSkellyCamAppState, null, 2)}
                </Typography>
            )}
            <h2 style={{ color: '#fafafa' }}>Available Camera Devices</h2>
            {availableCameras && (
                <Typography component="pre" style={{ color: '#fafafa' }}>
                    {JSON.stringify(availableCameras, null, 2)}
                </Typography>
            )}
        </Box>
    );
}
