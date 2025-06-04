import { Box, Collapse, useTheme } from "@mui/material";
import Grid from "@mui/material/Grid2"; // Updated import
import * as React from "react";
import { CameraConfigResolution } from "./CameraConfigResolution";
import { CameraConfigExposure } from "./CameraConfigExposure";
import { CameraConfigRotation } from "./CameraConfigRotation";
import { CameraConfig } from "@/store/slices/cameras-slices/camera-types";
import { useEffect, useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";

interface CameraConfigPanelProps {
  config: CameraConfig;
  onConfigChange: (newConfig: CameraConfig) => void;
  isExpanded: boolean;
}

export const CameraConfigPanel: React.FC<CameraConfigPanelProps> = ({
  config,
  onConfigChange,
  isExpanded,
}) => {
  const theme = useTheme();
  const [localConfig, setLocalConfig] = useState<CameraConfig>(config);
  // Debounce the local config changes with a 500ms delay
  const debouncedConfig = useDebounce<CameraConfig>(localConfig, 500);

  // Update local config when props change
  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  // Send the debounced config to the parent component for API updates
  useEffect(() => {
    // Only send updates if the config has actually changed
    if (JSON.stringify(debouncedConfig) !== JSON.stringify(config)) {
      onConfigChange(debouncedConfig);
    }
  }, [debouncedConfig, onConfigChange, config]);

  const handleChange = (field: keyof CameraConfig, value: any) => {
    // Update local state immediately for UI feedback
    const updatedConfig = {
      ...localConfig,
      [field]: value
    };
    
    setLocalConfig(updatedConfig);
  };

  return (
    <Collapse in={isExpanded}>
      <Box
        sx={{
          p: 1.5,
          ml: 7,
          mr: 2,
          mb: 1,
          borderRadius: 1,
          border: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <CameraConfigResolution
              resolution={config.resolution}
              onChange={(width, height) =>
                handleChange("resolution", { width, height })
              }
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <CameraConfigRotation
              rotation={config.rotation}
              onChange={(value) => handleChange("rotation", value)}
            />
          </Grid>
          <Grid size={12}>
            <CameraConfigExposure
              exposureMode={config.exposure_mode}
              exposure={config.exposure}
              onExposureModeChange={(mode) =>
                handleChange("exposure_mode", mode)
              }
              onExposureValueChange={(value) => handleChange("exposure", value)}
            />
          </Grid>
        </Grid>
      </Box>
    </Collapse>
  );
};
