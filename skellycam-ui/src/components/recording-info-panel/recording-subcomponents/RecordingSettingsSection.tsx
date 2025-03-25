// RecordingSettingsSection.tsx
import {Box, Checkbox, FormControlLabel, Stack, TextField} from "@mui/material";

interface SettingsSectionProps {
    useTimestamp: boolean;
    baseName: string;
    useIncrement: boolean;
    currentIncrement: number;
    createSubfolder: boolean;
    customSubfolderName: string;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingSettingsSection: React.FC<SettingsSectionProps> = ({
    useTimestamp,
    baseName,
    useIncrement,
    currentIncrement,
    createSubfolder,
    customSubfolderName,
    onUseTimestampChange,
    onBaseNameChange,
    onUseIncrementChange,
    onIncrementChange,
    onCreateSubfolderChange,
    onCustomSubfolderNameChange
}) => {
    return (
        <Stack spacing={2} sx={{pt: 1}}>
            {/* Base name input - always visible but disabled when timestamp is used */}
            <TextField
                label="Base Name"
                value={baseName}
                onChange={(e) => onBaseNameChange(e.target.value)}
                disabled={useTimestamp}
                fullWidth
                size="small"
            />

            {/* Custom subfolder input - always visible but disabled when not creating subfolder */}
            <TextField
                label="Custom Subfolder Name"
                value={customSubfolderName}
                onChange={(e) => onCustomSubfolderNameChange(e.target.value)}
                disabled={!createSubfolder}
                size="small"
                placeholder="Leave empty for timestamp"
                fullWidth
            />

            {/* Increment number - always visible but disabled when not using increment */}
            <TextField
                label="Auto Increment Number"
                value={currentIncrement}
                onChange={(e) => onIncrementChange(Math.max(1, parseInt(e.target.value) || 1))}
                disabled={!useIncrement}
                type="number"
                inputProps={{min: 1}}
                size="small"
                fullWidth
            />

            {/* Compact checkbox group */}
            <Box
                sx={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 1,
                }}
            >
                <FormControlLabel
                    control={
                        <Checkbox
                            checked={useTimestamp}
                            onChange={(e) => onUseTimestampChange(e.target.checked)}
                            size="small"
                        />
                    }
                    label="Use Timestamp"
                />

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={useIncrement}
                            onChange={(e) => onUseIncrementChange(e.target.checked)}
                            size="small"
                        />
                    }
                    label="Auto Increment"
                />

                <FormControlLabel
                    control={
                        <Checkbox
                            checked={createSubfolder}
                            onChange={(e) => onCreateSubfolderChange(e.target.checked)}
                            size="small"
                        />
                    }
                    label="Create Subfolder"
                />
            </Box>
        </Stack>
    );
};