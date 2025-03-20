import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {List, ListItem, ListItemText, Paper} from "@mui/material";
import {useAppSelector} from "@/store/hooks";

export const ConfigView = () => {
    const browserDetectedDevices = useAppSelector(state => state.cameras.browser_detected_devices);

    return (
        <Paper elevation={3} sx={{
            p: 2,
            backgroundColor: extendedPaperbaseTheme.palette.primary.dark,
            color: extendedPaperbaseTheme.palette.primary.contrastText
        }}>

            <List dense>
                {browserDetectedDevices.map(device => (
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
