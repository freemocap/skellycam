import {Box, darken, Typography} from "@mui/material";
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {useWebSocketContext} from "@/services/websocket-connection/WebSocketContext";
import {LogRecordSchema} from "@/types/zod-schemas/LogRecordSchema";
import {z} from "zod";
import {useEffect, useRef} from "react";

const LOG_LEVELS = ["LOOP", "TRACE", "DEBUG", "INFO", "SUCCESS", "API", "WARNING", "ERROR"] as const;
type LogLevel = typeof LOG_LEVELS[number];

const LOG_COLOR_CODES: Record<LogLevel, string> = {
    "LOOP": darken("#555555",.1),
    "TRACE": darken("#888888",.1),
    "DEBUG": darken("#3399FF",.1),
    "INFO": darken("#00E5FF",.1),
    "SUCCESS": darken("#FF66FF",.1),
    "API": darken("#66FF66",.1),
    "WARNING": darken("#FFFF66",.1),
    "ERROR": darken("#FF6666",.1),
};

export const TerminalPanelContent = () => {
    const {latestLogs} = useWebSocketContext();
    const logEndRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (logEndRef.current) {
            logEndRef.current.scrollIntoView({behavior: "smooth"});
        }
    }, [latestLogs]);

    return (
        <Box
            sx={{
                height: '100%',
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: darken(extendedPaperbaseTheme.palette.primary.dark,.75),
                borderColor: darken(extendedPaperbaseTheme.palette.primary.dark, .95),
                fontFamily: '"Courier New", monospace',
                fontSize: '14px',

            }}
        >
            <div style={{display: 'flex', justifyContent: "space-between", padding: '10px'}}>
                <span style={{color: extendedPaperbaseTheme.palette.primary.contrastText}}>Server Logs</span>
            </div>
            <div style={{flex: 1, overflowY: 'auto', padding: '10px'}}>
                {latestLogs && latestLogs.map((log: z.infer<typeof LogRecordSchema>, index) => {
                    const logLevel = log.levelname as LogLevel;
                    const color = (LOG_COLOR_CODES[logLevel]) || extendedPaperbaseTheme.palette.primary.contrastText;
                    const parts = log.formatted_message.split(log.msg);

                    return (
                        <Typography
                            key={index}
                            variant="body2"
                            sx={{
                                whiteSpace: 'nowrap',
                                marginBottom: '5px',
                            }}
                        >
                            <span style={{color: darken(extendedPaperbaseTheme.palette.primary.contrastText,.5)}}>{parts[0]}</span>
                            <span style={{color: color}}>{log.msg}</span>
                            <span style={{color: darken(extendedPaperbaseTheme.palette.primary.contrastText,.5)}}>{parts[1]}</span>
                        </Typography>
                    );
                })}
                <div ref={logEndRef}/>
                <Typography variant={"body2"} sx={{color: darken(extendedPaperbaseTheme.palette.primary.contrastText, .5)}}>
                    {'└>>...'}
                </Typography>
            </div>
        </Box>
    );
};
