import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {List, ListItem, ListItemText, Paper} from "@mui/material";
import {useDetectedDevicesContext} from "@/context/detectedDevicesContext";

export const ConfigView = () => {
    const { detectedDevices } = useDetectedDevicesContext();

    return (
        <Paper elevation={3} sx={{
            p: 2,
            backgroundColor: extendedPaperbaseTheme.palette.primary.dark,
            color: extendedPaperbaseTheme.palette.primary.contrastText
        }}>

            <List dense>
                {detectedDevices.map(device => (
                    <ListItem key={device.deviceId} sx={{ py: 0.5 }}>
                        <ListItemText
                            primary={device.label}
                            slotProps={{
                                primary: {
                                    sx: {
                                        color: extendedPaperbaseTheme.palette.primary.contrastText,
                                        fontSize: '0.875rem'
                                    }
                                }
                            }}
                        />
                    </ListItem>
                ))}
            </List>

        </Paper>
    );
}
