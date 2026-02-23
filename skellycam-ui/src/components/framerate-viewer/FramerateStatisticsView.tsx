// src/components/framerate-viewer/FramerateStatisticsView.tsx
import {
    Box,
    Divider,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tooltip,
    Typography,
} from "@mui/material";
import {alpha, useTheme} from "@mui/material/styles";
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {useState} from "react";
import {frontendColor, backendColor} from "@/components/framerate-viewer/FrameRateViewer";
import { useTranslation } from "react-i18next";

type FramerateStatisticsViewProps = {
    frontendFramerate: DetailedFramerate | null;
    backendFramerate: DetailedFramerate | null;
    compact?: boolean;
};

// Format number with fixed precision
const formatNumber = (num: number | null, precision = 3) => {
    return num !== null ? num.toFixed(precision) : "N/A";
};

type ProgressiveTooltipProps = {
    shortInfo: string;
    longInfo: string;
    children: React.ReactElement;
};

// Progressive tooltip component that shows more info on click
export const ProgressiveTooltip = ({
                                       shortInfo,
                                       longInfo,
                                       children,
                                   }: ProgressiveTooltipProps) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const theme = useTheme();
    const { t } = useTranslation();

    const handleTooltipClick = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsExpanded(!isExpanded);
    };

    return (
        <Tooltip
            title={
                <Box onClick={handleTooltipClick} sx={{cursor: "pointer"}}>
                    <Typography variant="body2">
                        {isExpanded ? longInfo : shortInfo}
                    </Typography>
                    <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{display: "block", mt: 1, textAlign: "center"}}
                    >
                        {isExpanded ? t("clickToShowLess") : t("clickToLearnMore")}
                    </Typography>
                </Box>
            }
            arrow
            placement="top"
            componentsProps={{
                tooltip: {
                    sx: {
                        backgroundColor: theme.palette.background.paper,
                        color: theme.palette.text.primary,
                        border: `1px solid ${theme.palette.divider}`,
                        boxShadow: theme.shadows[3],
                        maxWidth: isExpanded ? 500 : 300,
                        p: 1.5,
                    },
                },
            }}
        >
            {children}
        </Tooltip>
    );
};

type HeaderCellWithTooltipProps = {
    label: string;
    shortInfo: string;
    longInfo: string;
    style?: object;
    align?: "inherit" | "left" | "center" | "right" | "justify";
};

// Reusable tooltip component for column headers
export const HeaderCellWithTooltip = ({
                                          label,
                                          shortInfo,
                                          longInfo,
                                          style = {},
                                          align = "center",
                                      }: HeaderCellWithTooltipProps) => {
    return (
        <ProgressiveTooltip shortInfo={shortInfo} longInfo={longInfo}>
            <TableCell align={align} sx={style}>
                {label}
            </TableCell>
        </ProgressiveTooltip>
    );
};

type FramerateRowProps = {
    framerateData: DetailedFramerate | null;
    sourceColor: string;
    sourceLabel: string;
    colorMap: Record<string, string>;
    getCellStyle: (metricType: string) => object;
    shortTooltip: string;
    longTooltip: string;
};

const FramerateRow = ({
                          framerateData,
                          sourceColor,
                          sourceLabel,
                          colorMap,
                          getCellStyle,
                          shortTooltip,
                          longTooltip,
                      }: FramerateRowProps) => {
    const { t } = useTranslation();

    return (
        <TableRow>
            <ProgressiveTooltip shortInfo={shortTooltip} longInfo={longTooltip}>
                <TableCell
                    sx={{
                        fontWeight: "bold",
                        borderLeft: `4px solid ${sourceColor}`,
                        backgroundColor: `${sourceColor}22`,
                        paddingY: 0.5,
                        paddingLeft: 1,
                        color: sourceColor,
                        cursor: "help",
                    }}
                >
                    {framerateData?.framerate_source || sourceLabel}
                    <Typography
                        variant="caption"
                        display="block"
                        color="text.secondary"
                        sx={{fontSize: "0.6rem"}}
                    >
                        {framerateData?.calculation_window_size || 0} {t('samples')}
                    </Typography>
                </TableCell>
            </ProgressiveTooltip>

            <MetricCell
                label="current"
                colorMap={colorMap}
                getCellStyle={getCellStyle}
                primaryValue={framerateData?.mean_frames_per_second}
                primarySuffix="fps"
                secondaryValue={framerateData?.mean_frame_duration_ms}
                secondarySuffix="ms"
            />

            <MetricCell
                label="min"
                colorMap={colorMap}
                getCellStyle={getCellStyle}
                primaryValue={
                    framerateData?.frame_duration_max &&
                    framerateData.frame_duration_max > 0
                        ? 1000 / framerateData.frame_duration_max
                        : null
                }
                primarySuffix="fps"
                secondaryValue={framerateData?.frame_duration_max}
                secondarySuffix="ms"
            />

            <MetricCell
                label="max"
                colorMap={colorMap}
                getCellStyle={getCellStyle}
                primaryValue={
                    framerateData?.frame_duration_min &&
                    framerateData.frame_duration_min > 0
                        ? 1000 / framerateData.frame_duration_min
                        : null
                }
                primarySuffix="fps"
                secondaryValue={framerateData?.frame_duration_min}
                secondarySuffix="ms"
            />

            <MetricCell
                label="mean"
                colorMap={colorMap}
                getCellStyle={getCellStyle}
                primaryValue={framerateData?.frame_duration_mean && framerateData.frame_duration_mean > 0
                    ? 1000 / framerateData.frame_duration_mean
                    : null}
                primarySuffix="fps"
                secondaryValue={framerateData?.frame_duration_mean}
                secondarySuffix="ms"
            />

            <MetricCell
                label="median"
                colorMap={colorMap}
                getCellStyle={getCellStyle}
                primaryValue={framerateData?.frame_duration_median && framerateData.frame_duration_median > 0
                    ? 1000 / framerateData.frame_duration_median
                    : null}
                primarySuffix="fps"
                secondaryValue={framerateData?.frame_duration_median}
                secondarySuffix="ms"
            />

            <MetricCell
                label="stdDev"
                colorMap={colorMap}
                getCellStyle={getCellStyle}
                primaryValue={framerateData?.frame_duration_stddev}
                primarySuffix="ms"
                secondaryValue={
                    framerateData
                        ? framerateData.frame_duration_coefficient_of_variation * 100
                        : null
                }
                secondarySuffix="CV%"
            />
        </TableRow>
    );
};

type MetricCellProps = {
    label: string;
    colorMap: Record<string, string>;
    getCellStyle: (metricType: string) => object;
    primaryValue: number | null | undefined;
    primarySuffix?: string;
    secondaryValue?: number | null | undefined;
    secondarySuffix?: string;
};

const MetricCell = ({
                        label,
                        colorMap,
                        getCellStyle,
                        primaryValue,
                        primarySuffix = "",
                        secondaryValue,
                        secondarySuffix = "",
                    }: MetricCellProps) => {
    return (
        <TableCell align="center" sx={getCellStyle(label)}>
            <Typography
                fontWeight="bold"
                fontFamily="monospace"
                color={colorMap[label]}
                sx={{fontSize: "0.7rem", whiteSpace: "nowrap"}}
            >
                {formatNumber(primaryValue ?? null)} {primarySuffix}
            </Typography>
            {secondaryValue !== undefined && (
                <Typography
                    variant="caption"
                    color={colorMap[label]}
                    sx={{fontSize: "0.6rem", opacity: 0.9, whiteSpace: "nowrap"}}
                >
                    {formatNumber(secondaryValue ?? null)} {secondarySuffix}
                </Typography>
            )}
        </TableCell>
    );
};

export default function FramerateStatisticsView({
                                                    frontendFramerate,
                                                    backendFramerate,
                                                    compact = false,
                                                }: FramerateStatisticsViewProps) {
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === "dark";
    const { t } = useTranslation();

    // Define color map with high contrast for both light and dark themes
    const colorMap: Record<string, string> = {
        current: isDarkMode
            ? theme.palette.success.light
            : theme.palette.success.main,
        min: isDarkMode ? theme.palette.info.light : theme.palette.info.main,
        max: isDarkMode ? theme.palette.error.light : theme.palette.error.main,
        mean: isDarkMode ? theme.palette.warning.light : theme.palette.warning.main,
        median: isDarkMode
            ? theme.palette.warning.dark
            : theme.palette.warning.dark,
        stdDev: isDarkMode
            ? theme.palette.primary.light
            : theme.palette.primary.main,
        cv: isDarkMode
            ? theme.palette.secondary.light
            : theme.palette.secondary.main,
    };

    // Generate cell style based on metric type
    const getCellStyle = (metricType: string) => {
        return {
            backgroundColor: alpha(
                colorMap[metricType] || theme.palette.grey[500],
                isDarkMode ? 0.2 : 0.1
            ),
            borderBottom: "none",
            padding: "2px 4px",
        };
    };

    // Common header cell styles
    const headerCellStyle = {
        fontWeight: "bold",
        paddingY: 0.5,
    };

    // Tooltips content - short and long versions
    const tooltips = {
        source: {
            short: t("statsSourceShort"),
            long: t("statsSourceLong"),
        },
        current: {
            short: t("statsCurrentShort"),
            long: t("statsCurrentLong"),
        },
        min: {
            short: t("statsMinShort"),
            long: t("statsMinLong"),
        },
        max: {
            short: t("statsMaxShort"),
            long: t("statsMaxLong"),
        },
        mean: {
            short: t("statsMeanShort"),
            long: t("statsMeanLong"),
        },
        median: {
            short: t("statsMedianShort"),
            long: t("statsMedianLong"),
        },
        stdDev: {
            short: t("statsStdDevShort"),
            long: t("statsStdDevLong"),
        },
    };

    return (
        <TableContainer
            component={Paper}
            elevation={0}
            sx={{
                backgroundColor: "transparent",
                border: "none",
                overflowX: "auto",
            }}
        >
            <Table
                size="small"
                padding="none"
                sx={{
                    "& .MuiTableCell-root": {
                        fontSize: "0.65rem",
                        lineHeight: "1.1",
                        whiteSpace: "nowrap",
                    },
                }}
            >
                <TableHead>
                    <TableRow>
                        <HeaderCellWithTooltip
                            label={t("source")}
                            shortInfo={tooltips.source.short}
                            longInfo={tooltips.source.long}
                            style={{
                                ...headerCellStyle,
                                width: "12%",
                                color: theme.palette.text.primary,
                            }}
                            align="left"
                        />
                        <HeaderCellWithTooltip
                            label={t("current")}
                            shortInfo={tooltips.current.short}
                            longInfo={tooltips.current.long}
                            style={{
                                ...headerCellStyle,
                                ...getCellStyle("current"),
                            }}
                        />
                        <HeaderCellWithTooltip
                            label={t("min")}
                            shortInfo={tooltips.min.short}
                            longInfo={tooltips.min.long}
                            style={{
                                ...headerCellStyle,
                                ...getCellStyle("min"),
                            }}
                        />
                        <HeaderCellWithTooltip
                            label={t("max")}
                            shortInfo={tooltips.max.short}
                            longInfo={tooltips.max.long}
                            style={{
                                ...headerCellStyle,
                                ...getCellStyle("max"),
                            }}
                        />
                        <HeaderCellWithTooltip
                            label={t("mean")}
                            shortInfo={tooltips.mean.short}
                            longInfo={tooltips.mean.long}
                            style={{
                                ...headerCellStyle,
                                ...getCellStyle("mean"),
                            }}
                        />
                        <HeaderCellWithTooltip
                            label={t("median")}
                            shortInfo={tooltips.median.short}
                            longInfo={tooltips.median.long}
                            style={{
                                ...headerCellStyle,
                                ...getCellStyle("median"),
                            }}
                        />
                        <HeaderCellWithTooltip
                            label={t("stdDevCv")}
                            shortInfo={tooltips.stdDev.short}
                            longInfo={tooltips.stdDev.long}
                            style={{
                                ...headerCellStyle,
                                ...getCellStyle("stdDev"),
                            }}
                        />
                    </TableRow>
                    {/* Add the divider inside TableHead */}
                    <TableRow>
                        <TableCell colSpan={7} sx={{padding: 0}}>
                            <Divider sx={{borderColor: theme.palette.divider}}/>
                        </TableCell>
                    </TableRow>
                </TableHead>

                <TableBody>
                    {/* Server Row (primary - shown first) */}
                    <FramerateRow
                        framerateData={backendFramerate}
                        sourceColor={backendColor}
                        sourceLabel={t("server")}
                        colorMap={colorMap}
                        getCellStyle={getCellStyle}
                        shortTooltip={t("capturesFramesFromCamera")}
                        longTooltip="Server represents the camera frame-grabbing performance. This is the true rate at which frames are pulled from the camera and saved during recording. This is the most important metric for recording quality and should remain stable even if display performance fluctuates."
                    />

                    {/* Divider between rows */}
                    <TableRow>
                        <TableCell colSpan={7} sx={{padding: 0}}>
                            <Divider sx={{borderColor: theme.palette.divider}}/>
                        </TableCell>
                    </TableRow>

                    {/* Display Row */}
                    <FramerateRow
                        framerateData={frontendFramerate}
                        sourceColor={frontendColor}
                        sourceLabel={t("display")}
                        colorMap={colorMap}
                        getCellStyle={getCellStyle}
                        shortTooltip={t("rendersReceivedFrames")}
                        longTooltip={t("displayTooltipLong")}
                    />
                </TableBody>
            </Table>
        </TableContainer>
    );
}
