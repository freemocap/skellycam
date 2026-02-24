// src/components/framerate-viewer/FramerateTimeseriesView.tsx
import {useCallback} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {DetailedFramerate, TimestampedSample} from "@/services/server/server-helpers/framerate-store"
import {applyAxisStyles, createTooltip, renderEmptyChart} from "@/components/framerate-viewer/d3ChartUtils";
import BaseD3ChartView from "@/components/framerate-viewer/BaseD3ChartView";
import {useTranslation} from "react-i18next";

type FramerateTimeseriesProps = {
    frontendFramerate: DetailedFramerate | null
    backendFramerate: DetailedFramerate | null
    recentFrontendDurations: TimestampedSample[]
    recentBackendDurations: TimestampedSample[]
    frontendColor: string
    backendColor: string
    title?: string
}
type ChartRenderProps = {
    svg: d3.Selection<SVGGElement, unknown, null, undefined>;
    chartArea: d3.Selection<SVGGElement, unknown, null, undefined>;
    width: number;
    height: number;
    margin: { top: number; right: number; bottom: number; left: number };
    transform: d3.ZoomTransform;
};

/** How many seconds of data the rolling window shows. */
const WINDOW_SECONDS = 60;

export default function FramerateTimeseriesView({
                                                    frontendFramerate,
                                                    backendFramerate,
                                                    recentFrontendDurations,
                                                    recentBackendDurations,
                                                    frontendColor,
                                                    backendColor,
                                                    title = "Framerate Over Time"
                                                }: FramerateTimeseriesProps) {
    const theme = useTheme()
    const {t} = useTranslation()

    const renderChart = useCallback(({svg, chartArea, width, height, margin, transform}: ChartRenderProps) => {
        // Convert timestamped duration samples → timestamped FPS values
        const toFps = (samples: TimestampedSample[]): { timestamp: number; value: number }[] =>
            samples
                .filter(s => s.value > 0)
                .map(s => ({timestamp: s.timestamp, value: 1000 / s.value}));

        const sources = [
            {
                id: "frontend",
                name: frontendFramerate?.framerate_source || t("display"),
                color: frontendColor,
                data: toFps(recentFrontendDurations),
            },
            {
                id: "backend",
                name: backendFramerate?.framerate_source || t("server"),
                color: backendColor,
                data: toFps(recentBackendDurations),
            },
        ];

        if (sources.every((s) => s.data.length === 0)) {
            renderEmptyChart(svg, width, height, theme, t('waitingForData'));
            return;
        }

        // Determine the window from the actual data timestamps.
        // End = the most recent real timestamp; Start = end − WINDOW_SECONDS.
        const allTimestamps = sources.flatMap(s => s.data.map(d => d.timestamp));
        const latestTimestamp = Math.max(...allTimestamps);
        const windowEnd = latestTimestamp;
        const windowStart = windowEnd - WINDOW_SECONDS * 1000;

        // Only keep data points within the window
        const windowedSources = sources.map(s => ({
            ...s,
            data: s.data.filter(d => d.timestamp >= windowStart),
        }));

        const visibleData = windowedSources.flatMap(s => s.data);
        if (visibleData.length === 0) {
            renderEmptyChart(svg, width, height, theme, t('waitingForData'));
            return;
        }

        // Y domain from visible data
        const yMax = d3.max(visibleData, d => d.value) as number;
        const yMin = d3.min(visibleData, d => d.value) as number;
        const yRange = yMax - yMin;
        const yPadding = Math.max(1, yRange * 0.3);

        // Scales — x domain is anchored to the real data timestamps
        const xScale = d3.scaleTime()
            .domain([new Date(windowStart), new Date(windowEnd)])
            .range([0, width]);

        const yScale = d3.scaleLinear()
            .domain([Math.max(0, yMin - yPadding), yMax + yPadding])
            .range([height, 0]);

        // Apply zoom
        const xScaleZoomed = transform.rescaleX(xScale);
        const yScaleZoomed = transform.rescaleY(yScale);

        // Axes
        const xAxis = d3.axisBottom(xScaleZoomed)
            .ticks(Math.max(2, Math.min(5, Math.floor(width / 120))))
            .tickSize(-height)
            .tickFormat(d3.timeFormat("%H:%M:%S") as any);

        const yAxis = d3.axisLeft(yScaleZoomed)
            .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
            .tickSize(-width);

        svg.append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${height})`)
            .call(xAxis);

        svg.append("g")
            .attr("class", "y-axis")
            .call(yAxis);

        applyAxisStyles(svg, theme);

        // Line generator
        const line = d3.line<{ timestamp: number; value: number }>()
            .x(d => xScaleZoomed(new Date(d.timestamp)))
            .y(d => yScaleZoomed(d.value))
            .curve(d3.curveLinear);

        // Draw lines and dots
        windowedSources.forEach((source) => {
            if (source.data.length === 0) return;

            chartArea.append("path")
                .datum(source.data)
                .attr("fill", "none")
                .attr("stroke", source.color)
                .attr("stroke-width", 1.5)
                .attr("d", line);

            chartArea.selectAll(`.dot-${source.id}`)
                .data(source.data)
                .enter()
                .append("circle")
                .attr("class", `dot-${source.id}`)
                .attr("cx", d => xScaleZoomed(new Date(d.timestamp)))
                .attr("cy", d => yScaleZoomed(d.value))
                .attr("r", 2)
                .attr("fill", source.color)
                .attr("opacity", 0.8);
        });

        // Tooltip
        const tooltip = createTooltip(theme);

        windowedSources.forEach((source) => {
            if (source.data.length === 0) return;

            chartArea
                .selectAll(`.dot-${source.id}`)
                .on("mouseover", function (event: MouseEvent, d: any) {
                    const element = this as unknown as SVGCircleElement;
                    d3.select(element).attr("r", 5).attr("fill", d3.color(source.color)!.brighter(0.5).toString());

                    tooltip
                        .style("opacity", 1)
                        .html(`
              <div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                <span style="color: ${source.color};">${source.name}</span>
                <span style="color: ${theme.palette.text.secondary};">TIME:</span>
                <span>${new Date(d.timestamp).toISOString().substr(11, 12)}</span>
                <span style="color: ${theme.palette.text.secondary};">FPS:</span>
                <span>${d.value.toFixed(2)}</span>
                <span style="color: ${theme.palette.text.secondary};">DURATION:</span>
                <span>${(1000 / d.value).toFixed(2)} ms</span>
              </div>
            `)
                        .style("left", event.pageX + 10 + "px")
                        .style("top", event.pageY - 28 + "px");
                })
                .on("mouseout", function () {
                    d3.select(this).attr("r", 2).attr("fill", source.color);
                    tooltip.style("opacity", 0);
                });
        });

        return () => tooltip.remove();
    }, [
        frontendFramerate,
        backendFramerate,
        recentFrontendDurations,
        recentBackendDurations,
        frontendColor,
        backendColor,
        theme,
    ]);

    return (
        <BaseD3ChartView
            title={title}
            renderChart={renderChart}
            margin={{top: 20, right: 10, bottom: 35, left: 35}}
        />
    );
}
