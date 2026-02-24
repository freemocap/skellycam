// LogTerminal.tsx
import {
    alpha,
    Box,
    IconButton,
    TextField,
    ToggleButton,
    ToggleButtonGroup,
    Tooltip,
    useTheme,
} from "@mui/material";
import React, { useCallback, useEffect, useRef, useState } from "react";
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

/** Estimated height of a single collapsed log row in pixels. */
const ROW_HEIGHT = 28;

/** Extra rows rendered above/below the visible viewport. */
const OVERSCAN = 10;

const LOG_COLORS: Record<string, string> = {
    TRACE: "#ccc",
    DEBUG: "#88ccFF",
    INFO: "#00E5FF",
    SUCCESS: "#FF66FF",
    API: "#66FF66",
    WARNING: "#FFFF66",
    ERROR: "#FF6666",
    CRITICAL: "#FF0000",
};

// ---------------------------------------------------------------------------
// Lightweight log entry — plain divs instead of MUI Box / Chip / Collapse
// ---------------------------------------------------------------------------

const LogEntryRow = React.memo(({ log, style }: { log: LogRecord; style: React.CSSProperties }) => {
    const [expanded, setExpanded] = useState(false);
    const color = LOG_COLORS[log.levelname.toUpperCase()] || "#ccc";

    return (
        <div
            style={{
                ...style,
                // When expanded, override the fixed height so the detail panel is visible
                height: expanded ? "auto" : style.height,
                borderLeft: `2px solid ${color}`,
                paddingLeft: 8,
                backgroundColor: expanded ? `${color}1a` : "rgba(0,0,0,0.2)",
                cursor: "pointer",
                fontFamily: "monospace",
                fontSize: "0.85em",
                lineHeight: `${ROW_HEIGHT}px`,
                overflow: "hidden",
                whiteSpace: "nowrap",
                textOverflow: "ellipsis",
            }}
            onClick={() => setExpanded((prev) => !prev)}
        >
            {/* Collapsed single-line summary */}
            <span style={{ color: "#888", marginRight: 8, fontSize: "0.9em" }}>
                {log.asctime}
            </span>
            <span
                style={{
                    backgroundColor: color,
                    color: "#000",
                    padding: "1px 5px",
                    borderRadius: 2,
                    fontSize: "0.75em",
                    fontWeight: 600,
                    marginRight: 8,
                    display: "inline-block",
                    lineHeight: "normal",
                    verticalAlign: "middle",
                }}
            >
                {log.levelname}
            </span>
            <span style={{ color: "#fff" }}>{log.message}</span>

            {/* Expanded detail panel */}
            {expanded && (
                <LogEntryDetail log={log} color={color} />
            )}
        </div>
    );
});
LogEntryRow.displayName = "LogEntryRow";

const LogEntryDetail = ({ log, color }: { log: LogRecord; color: string }) => {
    const { t } = useTranslation();

    return (
        <div
            style={{
                paddingLeft: 16,
                paddingTop: 6,
                paddingBottom: 6,
                fontSize: "0.8em",
                color: "#888",
                borderTop: "1px solid rgba(255,255,255,0.1)",
                whiteSpace: "pre-wrap",
                lineHeight: "1.4",
                overflow: "visible",
            }}
            onClick={(e) => e.stopPropagation()}
        >
            <div>Location: {log.module}:{log.funcName}:Line#{log.lineno}</div>
            <div>{t("fileLabel")}: {log.filename}</div>
            <div>{t("timeDelta")}: {log.delta_t}</div>
            <div>{t("pathLabel")}: {log.pathname}</div>
            {log.formatted_message && (
                <div>{t("rawMessage")}: {log.formatted_message}</div>
            )}
            <div>Thread: {log.threadName} (ID: {log.thread})</div>
            <div>Process: {log.processName} (ID: {log.process})</div>
            {(log.exc_info || log.exc_text) && (
                <div>
                    <div>{t("exceptionDetails")}:</div>
                    {log.exc_info && <div>{log.exc_info}</div>}
                    {log.exc_text && <div>{log.exc_text}</div>}
                </div>
            )}
            {log.stack_info && (
                <div>
                    <div>{t("stackTrace")}:</div>
                    <pre
                        style={{
                            whiteSpace: "pre-wrap",
                            background: "#111",
                            padding: 8,
                            borderRadius: 4,
                            margin: "8px 0",
                        }}
                    >
                        {log.stack_info}
                    </pre>
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// LogTerminal
// ---------------------------------------------------------------------------

export const LogTerminal = () => {
    const theme = useTheme();
    const { t } = useTranslation();
    const { getLogStore } = useServer();

    const [snapshot, setSnapshot] = useState<LogSnapshot>({
        entries: [],
        hasErrors: false,
        countsByLevel: {},
        version: 0,
    });

    const [isPaused, setIsPaused] = useState(false);
    const [selectedLevels, setSelectedLevels] = useState<string[]>([]);
    const [searchText, setSearchText] = useState<string>("");
    const [showSearch, setShowSearch] = useState(false);
    const [copyFeedback, setCopyFeedback] = useState(false);

    // Virtualization state
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const [scrollTop, setScrollTop] = useState(0);
    const [containerHeight, setContainerHeight] = useState(0);
    const shouldAutoScroll = useRef(true);

    /** Track last snapshot version so we skip no-op polls. */
    const lastVersionRef = useRef(-1);

    // Poll the mutable LogStore on a fixed interval.
    useEffect(() => {
        if (isPaused) return;

        const poll = () => {
            const snap = getLogStore().getSnapshot();
            // Skip setState entirely if nothing changed — avoids React reconciliation
            if (snap.version === lastVersionRef.current) return;
            lastVersionRef.current = snap.version;
            setSnapshot(snap);
        };

        // Immediate snapshot when unpausing
        poll();

        const interval = setInterval(poll, LOG_POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [getLogStore, isPaused]);

    const filteredLogs = applyFilters(snapshot.entries, selectedLevels, searchText);

    // Track container height via ResizeObserver
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setContainerHeight(Math.round(entry.contentRect.height));
            }
        });
        observer.observe(container);
        return () => observer.disconnect();
    }, []);

    // Auto-scroll to bottom when new logs arrive
    useEffect(() => {
        if (!isPaused && shouldAutoScroll.current && scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
        }
    }, [filteredLogs, isPaused]);

    const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
        const el = e.currentTarget;
        setScrollTop(el.scrollTop);
        const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 50;
        shouldAutoScroll.current = isAtBottom;
    }, []);

    // Compute the visible window of log entries
    const totalHeight = filteredLogs.length * ROW_HEIGHT;
    const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
    const visibleCount = Math.ceil(containerHeight / ROW_HEIGHT) + 2 * OVERSCAN;
    const endIdx = Math.min(filteredLogs.length, startIdx + visibleCount);
    const offsetY = startIdx * ROW_HEIGHT;

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
        lastVersionRef.current = -1;
        setSnapshot({ entries: [], hasErrors: false, countsByLevel: {}, version: 0 });
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
            {/* Toolbar */}
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

            {/* Virtualized log list */}
            <div
                ref={scrollContainerRef}
                onScroll={handleScroll}
                style={{
                    flex: 1,
                    overflowY: "auto",
                    overflowX: "hidden",
                    position: "relative",
                    // Thin scrollbar styling via CSS properties
                    scrollbarWidth: "thin" as any,
                    scrollbarColor:
                        theme.palette.mode === "dark"
                            ? "rgba(255, 255, 255, 0.2) transparent"
                            : "rgba(0, 0, 0, 0.2) transparent",
                }}
            >
                {filteredLogs.length === 0 ? (
                    <div
                        style={{
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            height: "100%",
                            color: theme.palette.text.disabled,
                        }}
                    >
                        {isPaused ? t("loggingPaused") : t("noLogsToDisplay")}
                    </div>
                ) : (
                    // Outer div creates the full scrollable height
                    <div style={{ height: totalHeight, position: "relative" }}>
                        {/* Inner div is offset to the first visible row */}
                        <div
                            style={{
                                position: "absolute",
                                top: offsetY,
                                left: 0,
                                right: 0,
                            }}
                        >
                            {filteredLogs.slice(startIdx, endIdx).map((log, i) => (
                                <LogEntryRow
                                    key={`${log.created}-${log.thread}-${startIdx + i}`}
                                    log={log}
                                    style={{ height: ROW_HEIGHT }}
                                />
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </Box>
    );
};
