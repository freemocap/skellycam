// LogTerminal.tsx
import {
    alpha,
    Box,
    Chip,
    Collapse,
    IconButton,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    useTheme,
} from "@mui/material";
import { useCallback, useEffect, useRef, useState } from "react";
import { useServer } from "@/services/server/ServerContextProvider";
import { LogRecord, LogSnapshot } from "@/services/server/server-helpers/log-store";
import {
    DeleteSweep as DeleteSweepIcon,
    Pause as PauseIcon,
    PlayArrow as PlayArrowIcon,
    Search as SearchIcon,
    Warning as WarningIcon,
    ContentCopy as ContentCopyIcon,
    SaveAlt as SaveAltIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

const LOG_POLL_INTERVAL_MS = 500;

const LOG_COLORS = {
    TRACE: "#ccc",
    DEBUG: "#88ccFF",
    INFO: "#00E5FF",
    SUCCESS: "#FF66FF",
    API: "#66FF66",
    WARNING: "#FFFF66",
    ERROR: "#FF6666",
    CRITICAL: "#FF0000",
} as const;

const LogEntryComponent = ({ log }: { log: LogRecord }) => {
    const [expanded, setExpanded] = useState(false);
    const color =
        LOG_COLORS[log.levelname.toUpperCase() as keyof typeof LOG_COLORS] || "#ccc";
    const theme = useTheme();
    const { t } = useTranslation();

    const renderWithFormatting = (text: string | null | undefined): React.ReactNode => {
        if (!text) return null;

        return text.split("\n").map((line, i) => (
            <div
                key={i}
                style={{
                    whiteSpace: "pre-wrap",
                    fontFamily: "monospace",
                    lineHeight: "1.2",
                }}
            >
                {line}
            </div>
        ));
    };

    return (
        <Box
            sx={{
                mb: 0.5,
                borderLeft: `2px solid ${color}`,
                pl: 1,
                backgroundColor: expanded
                    ? alpha(color, 0.1)
                    : theme.palette.mode === "dark"
                        ? "rgba(0,0,0,0.2)"
                        : "rgba(0,0,0,0.05)",
                cursor: "pointer",
                transition: "background-color 0.1s",
                "&:hover": {
                    backgroundColor: alpha(
                        color,
                        theme.palette.mode === "dark" ? 0.05 : 0.1
                    ),
                },
            }}
            onClick={() => setExpanded(!expanded)}
        >
            <Box sx={{ display: "flex", gap: 1, alignItems: "center", py: 0.5 }}>
                <span
                    style={{
                        color: theme.palette.mode === "dark" ? "#888" : "#555",
                        fontSize: "0.9em",
                        minWidth: "140px",
                    }}
                >
                    {log.asctime}
                </span>
                <Chip
                    size="small"
                    label={log.levelname}
                    sx={{
                        backgroundColor: color,
                        color: "#000",
                        height: 16,
                        fontSize: "0.8em",
                        minWidth: "60px",
                        ".MuiChip-label": {
                            px: 1,
                        },
                    }}
                />
                <span
                    style={{
                        color: theme.palette.mode === "dark" ? "#fff" : "#000",
                        flexGrow: 1,
                        fontSize: "0.9em",
                    }}
                >
                    {renderWithFormatting(log.message)}
                </span>
            </Box>

            <Collapse in={expanded}>
                <Box
                    sx={{
                        pl: 2,
                        py: 1,
                        fontSize: "0.8em",
                        color: theme.palette.mode === "dark" ? "#888" : "#555",
                        borderTop: "1px solid",
                        fontFamily: 'monospace',
                        borderColor:
                            theme.palette.mode === "dark"
                                ? "rgba(255,255,255,0.1)"
                                : "rgba(0,0,0,0.1)",
                    }}
                >
                    <div>
                        Location: {log.module}:{log.funcName}:Line#{log.lineno}
                    </div>
                    <div>{t("fileLabel")}: {log.filename}</div>
                    <div>{t("timeDelta")}: {log.delta_t}</div>
                    <div>{t("pathLabel")}: {log.pathname}</div>
                    {log.formatted_message && (
                        <div>{t("rawMessage")}: {renderWithFormatting(log.formatted_message)}</div>
                    )}
                    <div>
                        Thread: {log.threadName} (ID: {log.thread})
                    </div>
                    <div>
                        Process: {log.processName} (ID: {log.process})
                    </div>

                    {(log.exc_info || log.exc_text) && (
                        <div>
                            <div>{t("exceptionDetails")}:</div>
                            {log.exc_info && <div>{renderWithFormatting(log.exc_info)}</div>}
                            {log.exc_text && <div>{renderWithFormatting(log.exc_text)}</div>}
                        </div>
                    )}

                    {log.stack_info && (
                        <div>
                            <div>{t("stackTrace")}:</div>
                            <pre
                                style={{
                                    whiteSpace: "pre-wrap",
                                    background:
                                        theme.palette.mode === "dark" ? "#111" : "#f5f5f5",
                                    padding: 8,
                                    borderRadius: 4,
                                    margin: "8px 0",
                                }}
                            >
                                {renderWithFormatting(log.stack_info)}
                            </pre>
                        </div>
                    )}
                </Box>
            </Collapse>
        </Box>
    );
};

function applyFilters(
    entries: LogRecord[],
    selectedLevels: string[],
    searchText: string,
): LogRecord[] {
    let filtered = entries;

    if (selectedLevels.length > 0) {
        filtered = filtered.filter(log =>
            selectedLevels.includes(log.levelname.toLowerCase())
        );
    }

    if (searchText) {
        const searchLower = searchText.toLowerCase();
        filtered = filtered.filter(log =>
            log.message.toLowerCase().includes(searchLower) ||
            log.module.toLowerCase().includes(searchLower) ||
            log.funcName.toLowerCase().includes(searchLower) ||
            log.formatted_message?.toLowerCase().includes(searchLower)
        );
    }

    return filtered;
}

export const LogTerminal = () => {
    const theme = useTheme();
    const { t } = useTranslation();
    const { getLogStore } = useServer();

    const [snapshot, setSnapshot] = useState<LogSnapshot>({
        entries: [],
        hasErrors: false,
        countsByLevel: {},
    });

    const [isPaused, setIsPaused] = useState(false);
    const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
    const [searchText, setSearchText] = useState<string>("");
    const [showSearch, setShowSearch] = useState(false);
    const logEndRef = useRef<HTMLDivElement>(null);
    const shouldAutoScroll = useRef(true);
    const [copyFeedback, setCopyFeedback] = useState(false);

    // Poll the mutable LogStore on a fixed interval.
    // When paused, stop polling so the displayed snapshot freezes in place.
    // Logs keep accumulating in the store regardless.
    useEffect(() => {
        if (isPaused) return;

        const interval = setInterval(() => {
            setSnapshot(getLogStore().getSnapshot());
        }, LOG_POLL_INTERVAL_MS);

        // Grab an immediate snapshot when unpausing
        setSnapshot(getLogStore().getSnapshot());

        return () => clearInterval(interval);
    }, [getLogStore, isPaused]);

    const filteredLogs = applyFilters(snapshot.entries, selectedLevels, searchText);

    const formatLogsForExport = useCallback((): string => {
        return filteredLogs.map((log) =>
            `[${log.asctime}] [${log.levelname}] ${log.module}:${log.funcName}:${log.lineno} - ${log.message}`
        ).join('\n');
    }, [filteredLogs]);

    const handleCopyToClipboard = useCallback(async () => {
        const text = formatLogsForExport();
        await navigator.clipboard.writeText(text);
        setCopyFeedback(true);
        setTimeout(() => setCopyFeedback(false), 2000);
    }, [formatLogsForExport]);

    const handleSaveToDisk = useCallback(() => {
        const text = formatLogsForExport();
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `skellycam-logs-${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [formatLogsForExport]);

    // Auto-scroll to bottom when new logs arrive (if not paused)
    useEffect(() => {
        if (!isPaused && shouldAutoScroll.current) {
            logEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [filteredLogs, isPaused]);

    const handleLevelToggle = (_: React.MouseEvent<HTMLElement>, newLevels: string[]): void => {
        setSelectedLevels(newLevels);
    };

    const handlePauseToggle = (): void => {
        setIsPaused(prev => !prev);
    };

    const handleClear = (): void => {
        getLogStore().clear();
        setSelectedLevels([]);
        setSearchText("");
        setShowSearch(false);
        setIsPaused(false);
        setSnapshot({ entries: [], hasErrors: false, countsByLevel: {} });
    };

    const handleScroll = (e: React.UIEvent<HTMLDivElement>): void => {
        const element = e.currentTarget;
        const isAtBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 50;
        shouldAutoScroll.current = isAtBottom;
    };

    return (
        <Box
            sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                backgroundColor:
                    theme.palette.mode === "dark" ? "#1a1a1a" : theme.palette.grey[100],
            }}
        >
            <Box
                sx={{
                    p: 0.5,
                    borderBottom: "1px solid",
                    borderColor: theme.palette.divider,
                    display: "flex",
                    gap: 1,
                    alignItems: "center",
                    flexWrap: "wrap",
                }}
            >
                <span
                    style={{
                        color: theme.palette.text.primary,
                        fontSize: "0.9em",
                        fontWeight: "bold",
                    }}
                >
                    {t('serverLogs')}
                </span>

                {snapshot.hasErrors && (
                    <Tooltip title={t("errorsDetected")}>
                        <WarningIcon
                            sx={{
                                color: LOG_COLORS.ERROR,
                                fontSize: "1.2em",
                                animation: "pulse 2s infinite",
                                "@keyframes pulse": {
                                    "0%, 100%": { opacity: 1 },
                                    "50%": { opacity: 0.5 },
                                },
                            }}
                        />
                    </Tooltip>
                )}

                <ToggleButtonGroup
                    size="small"
                    value={selectedLevels}
                    onChange={handleLevelToggle}
                    sx={{
                        ".MuiToggleButtonGroup-grouped": {
                            border: `1px solid ${theme.palette.divider} !important`,
                            mx: "1px",
                            "&:not(:first-of-type)": {
                                borderRadius: "2px",
                            },
                            "&:first-of-type": {
                                borderRadius: "2px",
                            },
                        },
                    }}
                >
                    {Object.entries(LOG_COLORS).map(([level, color]) => {
                        const count = snapshot.countsByLevel[level] || 0;
                        return (
                            <ToggleButton
                                key={level}
                                value={level.toLowerCase()}
                                sx={{
                                    py: 0.25,
                                    px: 1,
                                    minWidth: 0,
                                    fontSize: "0.75em",
                                    position: "relative",
                                    color: alpha(color, 0.7),
                                    "&.Mui-selected": {
                                        backgroundColor: alpha(color, 0.15),
                                        color: color,
                                        "&:hover": {
                                            backgroundColor: alpha(color, 0.2),
                                        },
                                    },
                                    "&:hover": {
                                        backgroundColor: alpha(color, 0.1),
                                    },
                                }}
                            >
                                {level}
                                {count > 0 && (
                                    <span
                                        style={{
                                            marginLeft: "4px",
                                            fontSize: "0.8em",
                                            opacity: 0.7,
                                        }}
                                    >
                                        ({count})
                                    </span>
                                )}
                            </ToggleButton>
                        );
                    })}
                </ToggleButtonGroup>

                <Box sx={{ ml: "auto", display: "flex", gap: 0.5 }}>
                    <Tooltip title={copyFeedback ? t("copied") : t("copyLogsToClipboard")}>
                        <IconButton
                            size="small"
                            onClick={handleCopyToClipboard}
                            sx={{ color: copyFeedback ? theme.palette.success.main : theme.palette.text.secondary }}
                        >
                            <ContentCopyIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title={t("saveLogsToFile")}>
                        <IconButton
                            size="small"
                            onClick={handleSaveToDisk}
                            sx={{ color: theme.palette.text.secondary }}
                        >
                            <SaveAltIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>

                    <IconButton
                        size="small"
                        onClick={() => setShowSearch(!showSearch)}
                        sx={{ color: theme.palette.text.secondary }}
                    >
                        <SearchIcon fontSize="small" />
                    </IconButton>

                    <IconButton
                        size="small"
                        onClick={handlePauseToggle}
                        sx={{
                            color: isPaused ? theme.palette.warning.main : theme.palette.text.secondary
                        }}
                    >
                        {isPaused ? <PlayArrowIcon fontSize="small" /> : <PauseIcon fontSize="small" />}
                    </IconButton>

                    <IconButton
                        size="small"
                        onClick={handleClear}
                        sx={{ color: theme.palette.text.secondary }}
                    >
                        <DeleteSweepIcon fontSize="small" />
                    </IconButton>
                </Box>
            </Box>

            {showSearch && (
                <Box sx={{ p: 1, borderBottom: "1px solid", borderColor: theme.palette.divider }}>
                    <TextField
                        size="small"
                        fullWidth
                        placeholder={t("searchLogs")}
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        InputProps={{
                            startAdornment: <SearchIcon sx={{ mr: 1, color: "text.secondary" }} />,
                        }}
                    />
                </Box>
            )}

            <Box
                sx={{
                    flex: 1,
                    overflowY: "auto",
                    p: 1,
                    "&::-webkit-scrollbar": {
                        width: "8px",
                        backgroundColor: "transparent",
                    },
                    "&::-webkit-scrollbar-thumb": {
                        backgroundColor:
                            theme.palette.mode === "dark"
                                ? "rgba(255, 255, 255, 0.2)"
                                : "rgba(0, 0, 0, 0.2)",
                        borderRadius: "4px",
                        "&:hover": {
                            backgroundColor:
                                theme.palette.mode === "dark"
                                    ? "rgba(255, 255, 255, 0.3)"
                                    : "rgba(0, 0, 0, 0.3)",
                        },
                    },
                    "&::-webkit-scrollbar-track": {
                        backgroundColor: "transparent",
                    },
                    // For Firefox
                    scrollbarWidth: "thin",
                    scrollbarColor:
                        theme.palette.mode === "dark"
                            ? "rgba(255, 255, 255, 0.2) transparent"
                            : "rgba(0, 0, 0, 0.2) transparent",
                }}
                onScroll={handleScroll}
            >
                {filteredLogs.length === 0 ? (
                    <Box
                        sx={{
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            height: "100%",
                            color: theme.palette.text.disabled,
                        }}
                    >
                        {isPaused ? t("loggingPaused") : t("noLogsToDisplay")}
                    </Box>
                ) : (
                    <>
                        {filteredLogs.map((log, i) => (
                            <LogEntryComponent key={`${log.created}-${log.thread}-${i}`} log={log} />
                        ))}
                        <div ref={logEndRef} />
                    </>
                )}
            </Box>
        </Box>
    );
};
