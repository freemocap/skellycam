import {Box, darken, Typography} from "@mui/material";
import IconButton from "@mui/material/IconButton";
import CloseIcon from '@mui/icons-material/Close';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {useWebSocketContext} from "@/context/WebSocketContext";
import {SkellyCamAppStateSchema} from "@/types/zod-schemas/SkellyCamAppStateSchema";
import {z} from "zod";

export const TerminalPanelContent = () => {
    const {latestLogs} = useWebSocketContext();

    return (
        <Box
            sx={{
                height: '100%',
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: extendedPaperbaseTheme.palette.primary.dark,
                borderStyle: 'solid',
                borderWidth: '20px',
                borderColor: darken(extendedPaperbaseTheme.palette.primary.dark, 0.9)
            }}
        >
            <div style={{display: 'flex', justifyContent: "space-between"}}>
                <span style={{color: extendedPaperbaseTheme.palette.primary.contrastText}}>Terminal</span>
                <IconButton size="small">
                    <CloseIcon fontSize="small" color={"primary"}/>
                </IconButton>
            </div>
            <div style={{flex: 1, overflowY: 'auto'}}>
                {latestLogs && latestLogs.map((log, index) => (
                    <Typography
                        key={index}
                        variant="body2"
                        sx={{
                            color: extendedPaperbaseTheme.palette.primary.contrastText,
                            padding: '10px',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {log.formatted_message}
                    </Typography>
                ))}
            </div>
        </Box>
    );
};
