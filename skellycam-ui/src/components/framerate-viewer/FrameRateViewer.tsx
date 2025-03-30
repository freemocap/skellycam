// src/components/framerate-viewer/FrameRateViewer.tsx
import { useState, useMemo } from "react"
import { Box, Typography, Paper, Grid, ToggleButtonGroup, ToggleButton, Divider } from "@mui/material"
import { alpha, useTheme } from "@mui/material/styles"
import FramerateTimeseriesView from "./FramerateTimeseriesView"
import FramerateHistogramView from "./FramerateHistogramView"
import StatisticsView from "./StatisticsView"
import { useAppSelector } from "@/store/AppStateStore"
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";

type ViewType = "timeseries" | "histogram" | "both"

export const FramerateViewerPanel = () => {
  const theme = useTheme()
  const [viewType, setViewType] = useState<ViewType>("both")

  const frontendFramerates = useAppSelector(state => state.framerateTracker.loggedFrontendFramerate)
  const backendFramerates = useAppSelector(state => state.framerateTracker.loggedBackendFramerate)

  // Transform frontend data for our components
  const frontendTimeseriesData = useMemo(() => {
    if (!frontendFramerates || frontendFramerates.length === 0) return []

    return frontendFramerates.map((entry, index) => ({
      timestamp: Date.now() - (frontendFramerates.length - index) * 1000, // Approximation
      value: entry.mean_frame_duration_ms || 0
    }))
  }, [frontendFramerates])

  // Transform backend data for our components
  const backendTimeseriesData = useMemo(() => {
    if (!backendFramerates || backendFramerates.length === 0) return []

    return backendFramerates.map((entry, index) => ({
      timestamp: Date.now() - (backendFramerates.length - index) * 1000, // Approximation
      value: entry.mean_frame_duration_ms || 0
    }))
  }, [backendFramerates])

  // Extract frontend histogram data
  const frontendHistogramData = useMemo(() => {
    if (!frontendFramerates || frontendFramerates.length === 0) return []

    return frontendFramerates
      .filter(entry => entry.mean_frame_duration_ms !== null)
      .map(entry => entry.mean_frame_duration_ms || 0)
  }, [frontendFramerates])

  // Extract backend histogram data
  const backendHistogramData = useMemo(() => {
    if (!backendFramerates || backendFramerates.length === 0) return []

    return backendFramerates
      .filter(entry => entry.mean_frame_duration_ms !== null)
      .map(entry => entry.mean_frame_duration_ms || 0)
  }, [backendFramerates])

  // Calculate frontend statistics
  const frontendStatistics = useMemo(() => {
    const values = frontendHistogramData

    if (values.length === 0) {
      return {
        min: 0,
        max: 0,
        avg: 0,
        stdDev: 0,
        current: 0,
        samples: 0
      }
    }

    const min = Math.min(...values)
    const max = Math.max(...values)
    const sum = values.reduce((a, b) => a + b, 0)
    const avg = sum / values.length
    const variance = values.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / values.length
    const stdDev = Math.sqrt(variance)
    const current = values[values.length - 1]

    return {
      min,
      max,
      avg,
      stdDev,
      current,
      samples: values.length
    }
  }, [frontendHistogramData])

  // Calculate backend statistics
  const backendStatistics = useMemo(() => {
    const values = backendHistogramData

    if (values.length === 0) {
      return {
        min: 0,
        max: 0,
        avg: 0,
        stdDev: 0,
        current: 0,
        samples: 0
      }
    }

    const min = Math.min(...values)
    const max = Math.max(...values)
    const sum = values.reduce((a, b) => a + b, 0)
    const avg = sum / values.length
    const variance = values.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / values.length
    const stdDev = Math.sqrt(variance)
    const current = values[values.length - 1]

    return {
      min,
      max,
      avg,
      stdDev,
      current,
      samples: values.length
    }
  }, [backendHistogramData])

  // Define time series data sources
  const timeseriesSources = [
    {
      id: "frontend",
      name: "Frontend Framerate",
      color: theme.palette.primary.main,
      data: frontendTimeseriesData
    },
    {
      id: "backend",
      name: "Backend Framerate",
      color: theme.palette.secondary.main,
      data: backendTimeseriesData
    }
  ]

  // Define histogram data sources
  const histogramSources = [
    {
      id: "frontend",
      name: "Frontend",
      color: theme.palette.primary.main,
      data: frontendHistogramData
    },
    {
      id: "backend",
      name: "Backend",
      color: theme.palette.secondary.main,
      data: backendHistogramData
    }
  ]

  return (
    <Box sx={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: theme.palette.background.default,
      p: 1
    }}>
      {/* Header with controls */}
      <Box sx={{
        pb: 1,
        mb: 1,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
          Camera Performance Metrics
        </Typography>

        {/* View type selector */}
        <ToggleButtonGroup
          size="small"
          exclusive
          value={viewType}
          onChange={(_, newValue) => {
            if (newValue !== null) setViewType(newValue);
          }}
        >
          <ToggleButton value="timeseries">Timeline</ToggleButton>
          <ToggleButton value="histogram">Distribution</ToggleButton>
          <ToggleButton value="both">Combined View</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Main content area with flexible layout based on view type */}
      <Grid container spacing={1} sx={{ flex: 1, overflow: 'hidden' }}>
        {/* Statistics panels */}
        <Grid item xs={12} sx={{ display: 'flex', gap: 1 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{
              pl: 1,
              borderLeft: `4px solid ${theme.palette.primary.main}`,
              color: theme.palette.primary.main
            }}>
              Frontend Frame Timing
            </Typography>
            <StatisticsView statistics={frontendStatistics} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{
              pl: 1,
              borderLeft: `4px solid ${theme.palette.secondary.main}`,
              color: theme.palette.secondary.main
            }}>
              Backend Frame Timing
            </Typography>
            <StatisticsView statistics={backendStatistics} />
          </Box>
        </Grid>

        {/* Visualization area */}
        {(viewType === 'timeseries' || viewType === 'both') && (
          <Grid item xs={12} md={viewType === 'both' ? 6 : 12} sx={{ height: viewType === 'both' ? 350 : 500 }}>
            <Paper
              elevation={0}
              sx={{
                height: '100%',
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                p: 1
              }}
            >
              <FramerateTimeseriesView
                sources={timeseriesSources}
                title="Frame Duration Timeline"
              />
            </Paper>
          </Grid>
        )}

        {(viewType === 'histogram' || viewType === 'both') && (
          <Grid item xs={12} md={viewType === 'both' ? 6 : 12} sx={{ height: viewType === 'both' ? 350 : 500 }}>
            <Paper
              elevation={0}
              sx={{
                height: '100%',
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                p: 1
              }}
            >
              <FramerateHistogramView
                sources={histogramSources}
                binCount={20}
                title="Frame Duration Distribution"
              />
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  )
}

export default FramerateViewerPanel
