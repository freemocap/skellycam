// src/components/framerate-viewer/StatisticsView.tsx
import { Box, Grid, Paper, Typography } from "@mui/material"
import { alpha, useTheme } from "@mui/material/styles"

type StatisticsPanelProps = {
  statistics: {
    min: number
    max: number
    avg: number
    stdDev: number
    current: number
    samples: number
  }
}

export default function StatisticsView({ statistics }: StatisticsPanelProps) {
  const theme = useTheme()
  const { min, max, avg, stdDev, current, samples } = statistics

  // Format number with fixed precision
  const formatNumber = (num: number) => {
    return num.toFixed(3)
  }

  // Calculate jitter (peak-to-peak)
  const jitter = max - min

  // Calculate coefficient of variation (CV)
  const cv = avg > 0 ? (stdDev / avg) * 100 : 0

  // Function to convert ms to FPS
  const msToFps = (ms: number) => {
    return ms > 0 ? 1000 / ms : 0
  }

  return (
    <Paper sx={{ p: 2, bgcolor: alpha(theme.palette.background.paper, 0.1), borderRadius: 1 }}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
        FRAME TIMING STATISTICS ({samples} SAMPLES)
      </Typography>

      <Grid container spacing={2}>
        <Grid item xs={6} md={2}>
          <Box sx={{ bgcolor: alpha(theme.palette.success.main, 0.1), p: 1, borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              CURRENT
            </Typography>
            <Typography variant="h6" fontWeight="bold" color={theme.palette.success.main} sx={{ fontFamily: "monospace" }}>
              {formatNumber(current)}
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                ms
              </Typography>
            </Typography>
            <Typography variant="caption" color={theme.palette.success.main}>
              {formatNumber(msToFps(current))} FPS
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6} md={2}>
          <Box sx={{ bgcolor: alpha(theme.palette.info.main, 0.1), p: 1, borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              MINIMUM
            </Typography>
            <Typography variant="h6" fontWeight="bold" color={theme.palette.info.main} sx={{ fontFamily: "monospace" }}>
              {formatNumber(min)}
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                ms
              </Typography>
            </Typography>
            <Typography variant="caption" color={theme.palette.info.main}>
              {formatNumber(msToFps(min))} FPS
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6} md={2}>
          <Box sx={{ bgcolor: alpha(theme.palette.error.main, 0.1), p: 1, borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              MAXIMUM
            </Typography>
            <Typography variant="h6" fontWeight="bold" color={theme.palette.error.main} sx={{ fontFamily: "monospace" }}>
              {formatNumber(max)}
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                ms
              </Typography>
            </Typography>
            <Typography variant="caption" color={theme.palette.error.main}>
              {formatNumber(msToFps(max))} FPS
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6} md={2}>
          <Box sx={{ bgcolor: alpha(theme.palette.warning.main, 0.1), p: 1, borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              AVERAGE
            </Typography>
            <Typography variant="h6" fontWeight="bold" color={theme.palette.warning.main} sx={{ fontFamily: "monospace" }}>
              {formatNumber(avg)}
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                ms
              </Typography>
            </Typography>
            <Typography variant="caption" color={theme.palette.warning.main}>
              {formatNumber(msToFps(avg))} FPS
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6} md={2}>
          <Box sx={{ bgcolor: alpha(theme.palette.primary.main, 0.1), p: 1, borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              STD DEV
            </Typography>
            <Typography variant="h6" fontWeight="bold" color={theme.palette.primary.main} sx={{ fontFamily: "monospace" }}>
              {formatNumber(stdDev)}
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                ms
              </Typography>
            </Typography>
            <Typography variant="caption" color={theme.palette.primary.main}>
              {formatNumber(cv)}% CV
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={6} md={2}>
          <Box sx={{ bgcolor: alpha(theme.palette.secondary.main, 0.1), p: 1, borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary" display="block">
              JITTER
            </Typography>
            <Typography variant="h6" fontWeight="bold" color={theme.palette.secondary.main} sx={{ fontFamily: "monospace" }}>
              {formatNumber(jitter)}
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                ms
              </Typography>
            </Typography>
            <Typography variant="caption" color={theme.palette.secondary.main}>
              P-P Variation
            </Typography>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  )
}
