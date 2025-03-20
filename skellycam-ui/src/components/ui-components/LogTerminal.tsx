import {Box, Chip, Collapse, darken, Stack, ToggleButton, ToggleButtonGroup, Tooltip, Typography} from "@mui/material";
import {useRef, useState} from "react";
import {useAppSelector} from "@/store/hooks";
import {LogEntry, LogSeverity} from "@/store/slices/logs-slice/LogsSlice";
import IconButton from "@mui/material/IconButton";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";

const LOG_LEVELS = ["LOOP", "TRACE", "DEBUG", "INFO", "SUCCESS", "API", "WARNING", "ERROR"] as const;
type LogLevel = typeof LOG_LEVELS[number];


const LOG_COLORS = {
    "LOOP": "#555555",
    "TRACE": "#888888",
    "DEBUG": "#3399FF",
    "INFO": "#00E5FF",
    "SUCCESS": "#FF66FF",
    "API": "#66FF66",
    "WARNING": "#FFFF66",
    "ERROR": "#FF6666"
} as const;

const LogEntryComponent = ({ log, showDetails }: { log: LogEntry, showDetails: boolean }) => {
    const [expanded, setExpanded] = useState(false);
    const color = LOG_COLORS[log.severity.toUpperCase() as keyof typeof LOG_COLORS];

    return (
        <Box sx={{ mb: 0.5, borderLeft: `2px solid ${color}`, pl: 1, backgroundColor: 'rgba(0,0,0,0.2)' }}>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <span style={{color: '#888'}}>{new Date(log.timestamp).toLocaleTimeString()}</span>
                <Chip size="small" label={log.severity} sx={{
                    backgroundColor: color,
                    color: '#000',
                    height: 20
                }}/>
                <span style={{color: '#fff', flexGrow: 1}}>{log.message}</span>
                {showDetails && (
                    <IconButton size="small" onClick={() => setExpanded(!expanded)} sx={{color: '#fff'}}>
                        <ExpandMoreIcon sx={{
                            transform: expanded ? 'rotate(180deg)' : 'none',
                            transition: '0.2s'
                        }}/>
                    </IconButton>
                )}
            </Box>

            {showDetails && (
                <Collapse in={expanded}>
                    <Box sx={{pl: 2, mt: 1, fontSize: '0.8em', color: '#888'}}>
                        <div>Module: {log.module} ({log.filename}:{log.lineNumber})</div>
                        <div>Function: {log.functionName}</div>
                        <div>Thread: {log.threadName} | Process: {log.processName}</div>
                        {log.stackTrace && (
                            <pre style={{
                                whiteSpace: 'pre-wrap',
                                background: '#111',
                                padding: 8,
                                borderRadius: 4
                            }}>{log.stackTrace}</pre>
                        )}
                    </Box>
                </Collapse>
            )}
        </Box>
    );
};

export const LogTerminal = () => {
    const logs = useAppSelector(state => state.logs.entries);
    const [selectedLevels, setSelectedLevels] = useState<LogSeverity[]>([]);
    const [showDetails, setShowDetails] = useState(false);
    const logEndRef = useRef<HTMLDivElement>(null);

    const filteredLogs = logs.filter(log =>
        selectedLevels.length === 0 || selectedLevels.includes(log.severity)
    );

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column', backgroundColor: '#1a1a1a'}}>
            <Box sx={{p: 1, borderBottom: '1px solid #333', display: 'flex', gap: 2}}>
                <span style={{color: '#fff'}}>Server Logs</span>
                <ToggleButtonGroup size="small" value={selectedLevels} onChange={(_, val) => setSelectedLevels(val)}>
                    {Object.entries(LOG_COLORS).map(([level, color]) => (
                        <ToggleButton key={level} value={level.toLowerCase()} sx={{
                            color: '#fff',
                            borderColor: '#444',
                            '&.Mui-selected': {
                                backgroundColor: darken(color, 0.6),
                                color: color
                            }
                        }}>
                            {level}
                        </ToggleButton>
                    ))}
                </ToggleButtonGroup>
                <Tooltip title="Toggle Details">
                    <IconButton size="small" onClick={() => setShowDetails(!showDetails)}
                                sx={{color: showDetails ? '#fff' : '#666'}}>
                        <ExpandMoreIcon />
                    </IconButton>
                </Tooltip>
            </Box>

            <Box sx={{flex: 1, overflowY: 'auto', p: 1}}>
                {filteredLogs.map((log, i) => (
                    <LogEntryComponent key={i} log={log} showDetails={showDetails} />
                ))}
                <div ref={logEndRef} />
            </Box>
        </Box>
    );
};
