import * as React from "react";
import {
    Alert,
    Box,
    Button,
    Fade,
    FormControl,
    IconButton,
    InputLabel,
    LinearProgress,
    MenuItem,
    Paper,
    Select,
    Stack,
    Tooltip,
    Typography,
    useTheme,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";

interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
}

interface ExecutablePathSelectorProps {
    onPathSelect: (path: string) => void;
    currentPath: string | null;
}

const truncatePath = (path: string, maxLength: number = 50): string => {
    if (path.length <= maxLength) return path;
    const start = path.substring(0, 20);
    const end = path.substring(path.length - 27);
    return `${start}...${end}`;
};

export const ExecutablePathSelector: React.FC<ExecutablePathSelectorProps> = ({
                                                                                  onPathSelect,
                                                                                  currentPath,
                                                                              }) => {
    const theme = useTheme();

    const [executableCandidates, setExecutableCandidates] = React.useState<
        ExecutableCandidate[]
    >([]);
    const [selectedExecutablePath, setSelectedExecutablePath] =
        React.useState<string>("");
    const [customExecutablePath, setCustomExecutablePath] =
        React.useState<string>("");
    const [isLoading, setIsLoading] = React.useState(false);
    const [showCustomInput, setShowCustomInput] = React.useState(false);

    React.useEffect(() => {
        loadExecutableInfo().then(r => {});
    }, []);

    const loadExecutableInfo = async () => {
        setIsLoading(true);
        try {
            const candidates =
                await window.electronAPI.getPythonServerExecutableCandidates();
            setExecutableCandidates(candidates);

            const validCandidate = candidates.find((c) => c.isValid);
            if (currentPath) {
                setSelectedExecutablePath(currentPath);
            } else if (validCandidate) {
                setSelectedExecutablePath(validCandidate.path);
            }
        } catch (error) {
            console.error("Error loading executable info:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleRefreshCandidates = async () => {
        setIsLoading(true);
        try {
            const candidates =
                await window.electronAPI.refreshPythonServerCandidates();
            setExecutableCandidates(candidates);
        } catch (error) {
            console.error("Error refreshing candidates:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSelectCustomExecutable = async () => {
        try {
            const selectedPath = await window.electronAPI.selectExecutableFile();
            if (selectedPath) {
                setCustomExecutablePath(selectedPath);
                setSelectedExecutablePath(selectedPath);
                onPathSelect(selectedPath);
                setShowCustomInput(false);
            }
        } catch (error) {
            console.error("Error selecting executable:", error);
        }
    };

    const handleSelectPath = (path: string) => {
        setSelectedExecutablePath(path);
        onPathSelect(path);
    };

    const getExecutableOptions = () => {
        const options = executableCandidates.map((candidate) => ({
            value: candidate.path,
            label: candidate.name,
            description: candidate.description,
            isValid: candidate.isValid,
            error: candidate.error,
        }));

        if (
            customExecutablePath &&
            !options.some((opt) => opt.value === customExecutablePath)
        ) {
            options.push({
                value: customExecutablePath,
                label: "Custom",
                description: customExecutablePath,
                isValid: undefined,
                error: undefined,
            });
        }

        return options;
    };

    if (isLoading) {
        return <LinearProgress sx={{mt: 2}}/>;
    }

    return (
        <Stack spacing={2}>
            {/* Current Path Display */}
            {/*{currentPath || true && (*/}
                <Paper
                    elevation={0}
                    sx={{
                        p: 1,
                        color: "text.primary",
                        border: "1px solid",
                        borderColor: "divider",
                    }}
                >
                    <Typography variant="caption" color="text.secondary" gutterBottom>
                        ACTIVE EXECUTABLE
                    </Typography>
                    <Tooltip title={currentPath} placement="top-start">
                        <Typography
                            variant="body2"
                            sx={{
                                fontFamily: "monospace",
                                color: theme.palette.primary.contrastText,

                                wordBreak: "break-all",
                            }}
                        >
                            {currentPath}
                            {/*{truncatePath(currentPath, 60)}*/}
                        </Typography>
                    </Tooltip>
                </Paper>
            {/*)}*/}

            {/* Path Selector */}
            <Box sx={{display: "flex", alignItems: "center", gap: 1}}>
                <FormControl fullWidth size="small">
                    <InputLabel id="executable-select-label">
                        Select Executable
                    </InputLabel>
                    <Select
                        labelId="executable-select-label"
                        value={selectedExecutablePath}
                        onChange={(e) => handleSelectPath(e.target.value)}
                        label="Select Executable"
                        disabled={isLoading}
                    >
                        {getExecutableOptions().map((option) => (
                            <MenuItem
                                key={option.value}
                                value={option.value}
                                disabled={option.isValid === false}
                            >
                                <Box sx={{width: "100%"}}>
                                    <Box sx={{display: "flex", alignItems: "center", gap: 1}}>
                                        {option.isValid === true && (
                                            <CheckCircleIcon color="success" fontSize="small"/>
                                        )}
                                        {option.isValid === false && (
                                            <ErrorIcon color="error" fontSize="small"/>
                                        )}
                                        <Typography variant="body2" fontWeight="medium">
                                            {option.label}
                                        </Typography>
                                    </Box>
                                    <Typography
                                        variant="caption"
                                        color="text.secondary"
                                        sx={{
                                            pl: option.isValid !== undefined ? 3.5 : 0,
                                            display: "block",
                                        }}
                                    >
                                        {truncatePath(option.description, 50)}
                                    </Typography>
                                </Box>
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>

                <Tooltip title="Add custom path">
                    <IconButton
                        onClick={() => setShowCustomInput(!showCustomInput)}
                        color={showCustomInput ? "primary" : "default"}
                    >
                        <AddCircleOutlineIcon/>
                    </IconButton>
                </Tooltip>

                <Tooltip title="Refresh candidates">
                    <IconButton onClick={handleRefreshCandidates} disabled={isLoading}>
                        <RefreshIcon/>
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Custom Path Input - Collapsible */}
            <Fade in={showCustomInput}>
                <Paper
                    elevation={1}
                    sx={{
                        p: 2,
                        display: showCustomInput ? "block" : "none",
                        bgcolor: "background.paper",
                    }}
                >
                    <Typography variant="caption" color="text.secondary" gutterBottom>
                        CUSTOM EXECUTABLE PATH
                    </Typography>
                    <Box sx={{display: "flex", gap: 1, mt: 1}}>
                        <Button
                            variant="outlined"
                            startIcon={<FolderOpenIcon/>}
                            onClick={handleSelectCustomExecutable}
                            fullWidth
                            sx={{
                                color: theme.palette.primary.contrastText,
                                borderColor: theme.palette.primary.contrastText,
                            }}
                        >
                            Browse for Executable
                        </Button>
                    </Box>
                </Paper>
            </Fade>

            {/* Error Display */}
            {selectedExecutablePath &&
                (() => {
                    const selectedCandidate = executableCandidates.find(
                        (c) => c.path === selectedExecutablePath
                    );
                    if (selectedCandidate?.isValid === false) {
                        return (
                            <Alert severity="error" variant="outlined" sx={{mt: 1}}>
                                <Typography variant="caption">
                                    {selectedCandidate.error}
                                </Typography>
                            </Alert>
                        );
                    }
                    return null;
                })()}
        </Stack>
    );
};
