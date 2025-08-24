// skellycam-ui/src/components/recording-info-panel/RecordingInfoPanel.tsx
import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  useTheme
} from '@mui/material';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import VideocamIcon from '@mui/icons-material/Videocam';
import SettingsIcon from '@mui/icons-material/Settings';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import FolderIcon from '@mui/icons-material/Folder';
import { useAppDispatch, useAppSelector } from "@/store/AppStateStore";
import { RecordingSettingsSection } from "@/components/recording-info-panel/recording-subcomponents/RecordingSettingsSection";
import { StartStopRecordingButton } from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import { DelayRecordingStartControl } from "@/components/recording-info-panel/recording-subcomponents/DelayRecordingStartControl";
import { FullRecordingPathPreview } from "@/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview";
import { BaseRecordingDirectoryInput } from "@/components/recording-info-panel/recording-subcomponents/BaseRecordingDirectoryInput";
import { RecordingNamePreview } from "@/components/recording-info-panel/recording-subcomponents/RecordingNamePreview";
import { startRecording, stopRecording } from "@/store/thunks/start-stop-recording-thunks";
import { setRecordingInfo } from "@/store/slices/recordingInfoSlice";

export const TreeViewRecordingInfoPanel: React.FC = () => {
  const theme = useTheme();
  const dispatch = useAppDispatch();
  const recordingInfo = useAppSelector(state => state.recordingStatus.currentRecordingInfo);

  // Local UI state
  const [showSettings, setShowSettings] = useState(true);
  const [createSubfolder, setCreateSubfolder] = useState(false);
  const [useDelayStart, setUseDelayStart] = useState(false);
  const [delaySeconds, setDelaySeconds] = useState(3);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [recordingTag, setRecordingTag] = useState('');

  // Local recording naming preferences
  const [useTimestamp, setUseTimestamp] = useState(true);
  const [useIncrement, setUseIncrement] = useState(false);
  const [currentIncrement, setCurrentIncrement] = useState(1);
  const [baseName, setBaseName] = useState('recording');
  const [customSubfolderName, setCustomSubfolderName] = useState('');

  // replace ~ with user's home directory
  useEffect(() => {
    if (recordingInfo?.recordingDirectory?.startsWith('~')) {
      window.electronAPI.getHomeDirectory().then(
        (homePath: string) => {
          const updatedDirectory = recordingInfo.recordingDirectory.replace('~', homePath);
          dispatch(setRecordingInfo({ recordingDirectory: updatedDirectory }));
        }
      );
    }
  }, [recordingInfo, dispatch]);

  // Handle countdown timer
  useEffect(() => {
    if (countdown !== null && countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    } else if (countdown === 0) {
      handleStartRecording();
      setCountdown(null);
    }
  }, [countdown]);

  const getTimestampString = (): string => {
    const now = new Date();

    // Format date in local time with timezone info
    const dateOptions: Intl.DateTimeFormatOptions = {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZoneName: 'shortOffset'
    };

    // Get formatted parts
    const formatter = new Intl.DateTimeFormat('en-US', dateOptions);
    const parts = formatter.formatToParts(now);

    // Create a map of the parts for easy access
    const partMap: Record<string, string> = {};
    parts.forEach(part => {
      partMap[part.type] = part.value;
    });

    // Build the timestamp string in a filename-friendly format
    const timestamp = `${partMap.year}-${partMap.month}-${partMap.day}_${partMap.hour}-${partMap.minute}-${partMap.second}_${partMap.timeZoneName.replace(':', '')}`;

    return timestamp;
  };

  const buildRecordingName = (): string => {
    const parts: string[] = [];

    // Base name component
    if (useTimestamp) {
      parts.push(getTimestampString());
    } else {
      parts.push(baseName);
    }

    // Add tag if present
    if (recordingTag) {
      parts.push(recordingTag);
    }

    return parts.join('_');
  };

  const handleStartRecording = () => {
    console.log('Starting recording...');

    const recordingName = buildRecordingName();
    const subfolderName = createSubfolder ? (customSubfolderName || getTimestampString()) : '';
    const recordingPath = createSubfolder
      ? `${recordingInfo.recordingDirectory}/${subfolderName}`
      : recordingInfo.recordingDirectory;

    console.log('Recording path:', recordingPath);
    console.log('Recording name:', recordingName);

    if (useIncrement) {
      setCurrentIncrement(prev => prev + 1);
    }

    dispatch(startRecording({
      recordingName,
      recordingDirectory: recordingPath
    }));
  };

  const handleButtonClick = () => {
    if (recordingInfo.isRecording) {
      console.log('Stopping recording...');
      dispatch(stopRecording());
    } else if (useDelayStart) {
      console.log(`Starting countdown from ${delaySeconds} seconds`);
      setCountdown(delaySeconds);
    } else {
      handleStartRecording();
    }
  };

  return (
    <Box sx={{
      padding: 2,
      color: 'text.primary',
      bgcolor: theme.palette.background.paper,
      borderRadius: 1,
      mb: 2
    }}>
      <SimpleTreeView
        defaultExpandedItems={['recording-main']}
        slots={{
          collapseIcon: ExpandMoreIcon,
          expandIcon: ChevronRightIcon
        }}
        sx={{ flexGrow: 1 }}
      >
        <TreeItem
          itemId="recording-main"
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', pr: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <VideocamIcon />
                <span>Record Videos</span>

              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                {/* Moved Start/Stop button to top row */}
                <StartStopRecordingButton
                  isRecording={recordingInfo.isRecording}
                  countdown={countdown}
                  onClick={handleButtonClick}

                />
              </Box>
            </Box>
          }
        >
          <Box sx={{ pl: 2, pt: 1, borderTop: '2px solid', borderColor: 'primary.main' }}>
              <FullRecordingPathPreview
                  directory={recordingInfo.recordingDirectory}
                  filename={buildRecordingName()}
                  subfolder={createSubfolder ? (customSubfolderName || getTimestampString()) : undefined}
              />
              {/* Countdown display in controls section */}
              {countdown !== null && (
                  <Typography variant="h4" align="center" color="secondary">
                      Starting in {countdown}...
                  </Typography>
              )}


              <Box sx={{ pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>


                <DelayRecordingStartControl
                  useDelay={useDelayStart}
                  delaySeconds={delaySeconds}
                  onDelayToggle={setUseDelayStart}
                  onDelayChange={setDelaySeconds}
                />
              </Box>

              <Box sx={{ pl: 2, pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <BaseRecordingDirectoryInput
                  value={recordingInfo.recordingDirectory}
                />

                <RecordingNamePreview
                  name={buildRecordingName()}
                  tag={recordingTag}
                  isRecording={recordingInfo.isRecording}
                  onTagChange={setRecordingTag}
                />

                <RecordingSettingsSection
                  useTimestamp={useTimestamp}
                  baseName={baseName}
                  useIncrement={useIncrement}
                  currentIncrement={currentIncrement}
                  createSubfolder={createSubfolder}
                  customSubfolderName={customSubfolderName}
                  onUseTimestampChange={setUseTimestamp}
                  onBaseNameChange={setBaseName}
                  onUseIncrementChange={setUseIncrement}
                  onIncrementChange={setCurrentIncrement}
                  onCreateSubfolderChange={setCreateSubfolder}
                  onCustomSubfolderNameChange={setCustomSubfolderName}
                />
              </Box>
          </Box>
        </TreeItem>
      </SimpleTreeView>
    </Box>
  );
};
