// src/components/framerate-viewer/FramerateStatisticsView.tsx
import { Box, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material"
import { alpha, useTheme } from "@mui/material/styles"
import {CurrentFramerate} from "@/store/slices/framerateTrackerSlice";

type FramerateStatisticsViewProps = {
  frontendFramerate: CurrentFramerate | null,
  backendFramerate: CurrentFramerate | null,
  compact?: boolean
}

export default function FramerateStatisticsView({ frontendFramerate, backendFramerate, compact = false }: FramerateStatisticsViewProps) {
  const theme = useTheme()
  const isDarkMode = theme.palette.mode === 'dark'

  // Format number with fixed precision
  const formatNumber = (num: number | null) => {
    return num !== null ? num.toFixed(1) : 'N/A'
  }

  // Define color map with high contrast for both light and dark themes
  const colorMap: Record<string, string> = {
    'current': isDarkMode ? theme.palette.success.light : theme.palette.success.main,
    'min': isDarkMode ? theme.palette.info.light : theme.palette.info.main,
    'max': isDarkMode ? theme.palette.error.light : theme.palette.error.main,
    'avg': isDarkMode ? theme.palette.warning.light : theme.palette.warning.main,
    'stdDev': isDarkMode ? theme.palette.primary.light : theme.palette.primary.main,
    'cv': isDarkMode ? theme.palette.secondary.light : theme.palette.secondary.main
  }

  // Generate cell style based on metric type
  const getCellStyle = (metricType: string) => {
    return {
      backgroundColor: alpha(colorMap[metricType] || theme.palette.grey[500], isDarkMode ? 0.2 : 0.1),
      borderBottom: 'none',
      padding: '2px 4px',
    }
  }

  return (
      <TableContainer component={Paper} elevation={0} sx={{
        backgroundColor: 'transparent',
        border: 'none',
        overflowX: 'auto'
      }}>
        <Table size="small" padding="none" sx={{
          '& .MuiTableCell-root': {
            fontSize: '0.65rem',
            lineHeight: '1.1',
            whiteSpace: 'nowrap'
          }
        }}>
          <TableHead>
            <TableRow>
              <TableCell sx={{
                fontWeight: 'bold',
                width: '12%',
                paddingY: 0.5,
                color: theme.palette.text.primary
              }}>Source</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', ...getCellStyle('current'), paddingY: 0.5 }}>Current</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', ...getCellStyle('min'), paddingY: 0.5 }}>Min</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', ...getCellStyle('max'), paddingY: 0.5 }}>Max</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', ...getCellStyle('avg'), paddingY: 0.5 }}>Avg</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', ...getCellStyle('stdDev'), paddingY: 0.5 }}>StdDev</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', ...getCellStyle('cv'), paddingY: 0.5 }}>CV %</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {/* Frontend Row */}
            <TableRow>
              <TableCell
                  sx={{
                    fontWeight: 'bold',
                    borderLeft: `3px solid ${colorMap.current}`,
                    paddingY: 0.5,
                    color: isDarkMode ? theme.palette.primary.light : theme.palette.primary.main
                  }}
              >
                {frontendFramerate?.framerate_source || "Frontend"}
                <Typography
                    variant="caption"
                    display="block"
                    color="text.secondary"
                    sx={{ fontSize: '0.6rem' }}
                >
                  {frontendFramerate?.calculation_window_size || 0} samples
                </Typography>
              </TableCell>

              {/* Current */}
              <TableCell align="center" sx={getCellStyle('current')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.current}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {frontendFramerate ? formatNumber(frontendFramerate.mean_frame_duration_ms) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.current}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {frontendFramerate ? formatNumber(frontendFramerate.mean_frames_per_second) : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* Min */}
              <TableCell align="center" sx={getCellStyle('min')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.min}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {frontendFramerate ? formatNumber(frontendFramerate.frame_duration_min) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.min}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {frontendFramerate && frontendFramerate.frame_duration_min > 0
                      ? formatNumber(1000 / frontendFramerate.frame_duration_min)
                      : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* Max */}
              <TableCell align="center" sx={getCellStyle('max')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.max}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {frontendFramerate ? formatNumber(frontendFramerate.frame_duration_max) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.max}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {frontendFramerate && frontendFramerate.frame_duration_max > 0
                      ? formatNumber(1000 / frontendFramerate.frame_duration_max)
                      : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* Avg */}
              <TableCell align="center" sx={getCellStyle('avg')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.avg}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {frontendFramerate ? formatNumber(frontendFramerate.frame_duration_mean) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.avg}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {frontendFramerate && frontendFramerate.frame_duration_mean > 0
                      ? formatNumber(1000 / frontendFramerate.frame_duration_mean)
                      : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* StdDev */}
              <TableCell align="center" sx={getCellStyle('stdDev')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.stdDev}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {frontendFramerate ? formatNumber(frontendFramerate.frame_duration_stddev) : 'N/A'}
                </Typography>
              </TableCell>

              {/* Coefficient of Variation */}
              <TableCell align="center" sx={getCellStyle('cv')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.cv}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {frontendFramerate
                      ? formatNumber(frontendFramerate.frame_duration_coefficient_of_variation * 100)
                      : 'N/A'}
                </Typography>
              </TableCell>
            </TableRow>

            {/* Backend Row */}
            <TableRow>
              <TableCell
                  sx={{
                    fontWeight: 'bold',
                    borderLeft: `3px solid ${colorMap.current}`,
                    paddingY: 0.5,
                    color: isDarkMode ? theme.palette.secondary.light : theme.palette.secondary.main
                  }}
              >
                {backendFramerate?.framerate_source || "Backend"}
                <Typography
                    variant="caption"
                    display="block"
                    color="text.secondary"
                    sx={{ fontSize: '0.6rem' }}
                >
                  {backendFramerate?.calculation_window_size || 0} samples
                </Typography>
              </TableCell>

              {/* Current */}
              <TableCell align="center" sx={getCellStyle('current')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.current}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {backendFramerate ? formatNumber(backendFramerate.mean_frame_duration_ms) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.current}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {backendFramerate ? formatNumber(backendFramerate.mean_frames_per_second) : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* Min */}
              <TableCell align="center" sx={getCellStyle('min')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.min}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {backendFramerate ? formatNumber(backendFramerate.frame_duration_min) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.min}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {backendFramerate && backendFramerate.frame_duration_min > 0
                      ? formatNumber(1000 / backendFramerate.frame_duration_min)
                      : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* Max */}
              <TableCell align="center" sx={getCellStyle('max')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.max}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {backendFramerate ? formatNumber(backendFramerate.frame_duration_max) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.max}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {backendFramerate && backendFramerate.frame_duration_max > 0
                      ? formatNumber(1000 / backendFramerate.frame_duration_max)
                      : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* Avg */}
              <TableCell align="center" sx={getCellStyle('avg')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.avg}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {backendFramerate ? formatNumber(backendFramerate.frame_duration_mean) : 'N/A'}
                </Typography>
                <Typography
                    variant="caption"
                    color={colorMap.avg}
                    sx={{ fontSize: '0.6rem', opacity: 0.9 }}
                >
                  {backendFramerate && backendFramerate.frame_duration_mean > 0
                      ? formatNumber(1000 / backendFramerate.frame_duration_mean)
                      : 'N/A'} fps
                </Typography>
              </TableCell>

              {/* StdDev */}
              <TableCell align="center" sx={getCellStyle('stdDev')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.stdDev}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {backendFramerate ? formatNumber(backendFramerate.frame_duration_stddev) : 'N/A'}
                </Typography>
              </TableCell>

              {/* Coefficient of Variation */}
              <TableCell align="center" sx={getCellStyle('cv')}>
                <Typography
                    fontWeight="bold"
                    fontFamily="monospace"
                    color={colorMap.cv}
                    sx={{ fontSize: '0.7rem' }}
                >
                  {backendFramerate
                      ? formatNumber(backendFramerate.frame_duration_coefficient_of_variation * 100)
                      : 'N/A'}
                </Typography>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
  )
}
