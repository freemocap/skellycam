// src/components/framerate-viewer/FramerateTimeseriesView.tsx
import {useCallback} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {DetailedFramerate} from "@/services/server/framerate-store"
import {applyAxisStyles, createTooltip, renderEmptyChart} from "@/components/framerate-viewer/d3ChartUtils";
import BaseD3ChartView from "@/components/framerate-viewer/BaseD3ChartView";

type FramerateTimeseriesProps = {
    frontendFramerate: DetailedFramerate | null
    backendFramerate: DetailedFramerate | null
    recentFrontendFrameDurations: number[]
    recentBackendFrameDurations: number[]
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

export default function FramerateTimeseriesView({
                                                    frontendFramerate,
                                                    backendFramerate,
                                                    recentFrontendFrameDurations,
                                                    recentBackendFrameDurations,
                                                    frontendColor,
                                                    backendColor,
                                                    title = "Framerate Over Time"
                                                }: FramerateTimeseriesProps) {
    const theme = useTheme()

    const renderChart = useCallback(({svg, chartArea, width, height, margin, transform}: ChartRenderProps) => {
        // Each data point in recentFrameDurations arrives ~1 second apart (server throttle rate)
        const UPDATE_INTERVAL_MS = 1000;

        const sources = [
            {
                id: "frontend",
                name: frontendFramerate?.framerate_source || "Display",
                color: frontendColor,
                data: recentFrontendFrameDurations
                    .filter(v => v > 0)
                    .map((value, index, arr) => ({
                        timestamp: Date.now() - (arr.length - index) * UPDATE_INTERVAL_MS,
                        value: 1000 / value
                    }))
            },
            {
                id: "backend",
                name: backendFramerate?.framerate_source || "Server",
                color: backendColor,
                data: recentBackendFrameDurations
                    .filter(v => v > 0)
                    .map((value, index, arr) => ({
                        timestamp: Date.now() - (arr.length - index) * UPDATE_INTERVAL_MS,
                        value: 1000 / value
                    }))
            }
        ];

        if (sources.every((s) => s.data.length === 0)) {
            renderEmptyChart(svg, width, height, theme);
            return;
        }

        // Combine all data points to determine overall domain
        const allData = sources.flatMap((s) => s.data);

        // Set up scales
        const xScale = d3
            .scaleTime()
            .domain(d3.extent(allData, (d) => new Date(d.timestamp)) as [Date, Date])
            .range([0, width]);

        // Calculate y domain zoomed to actual data range
        const yMax = d3.max(allData, (d) => d.value) as number;
        const yMin = d3.min(allData, (d) => d.value) as number;
        const yRange = yMax - yMin;
        const yPadding = Math.max(1, yRange * 0.3);

        const yScale = d3
            .scaleLinear()
            .domain([Math.max(0, yMin - yPadding), yMax + yPadding])
            .range([height, 0]);

        // Apply the current zoom transform
        const xScaleZoomed = transform.rescaleX(xScale);
        const yScaleZoomed = transform.rescaleY(yScale);

        // Create axes
        const xAxis = d3
            .axisBottom(xScaleZoomed)
            .ticks(5)
            .tickSize(-height)
            .tickFormat(d3.timeFormat("%H:%M:%S") as any);

        const yAxis = d3.axisLeft(yScaleZoomed).ticks(10).tickSize(-width);

        // Add X axis
        const xAxisGroup = svg
            .append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${height})`)
            .call(xAxis);

        xAxisGroup
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-45)");

        // Add Y axis
        const yAxisGroup = svg
            .append("g")
            .attr("class", "y-axis")
            .call(yAxis);

        // Add Y axis label
        svg
            .append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", 0 - margin.left)
            .attr("x", 0 - height / 2)
            .attr("dy", "1em")
            .style("text-anchor", "middle")
            .style("font-family", "monospace")
            .style("font-size", "14px")
            .style("fill", theme.palette.text.secondary)
            .text("Framerate (fps)");

        // Style axes
        applyAxisStyles(svg, theme);

        // Add threshold lines
        // const thresholds = [
        //   { value: 16.67, label: "60 FPS", color: theme.palette.success.main },
        //   { value: 33.33, label: "30 FPS", color: theme.palette.warning.main },
        // ];
        //
        // renderThresholdLines(chartArea, thresholds, xScaleZoomed, yScaleZoomed, width, height, true);

        // Create line generator
        const line = d3
            .line<{ timestamp: number, value: number }>()
            .x((d) => xScaleZoomed(new Date(d.timestamp)))
            .y((d) => yScaleZoomed(d.value))
            .curve(d3.curveLinear);

        // Add lines and points for each source
        sources.forEach((source) => {
            if (source.data.length === 0) return;

            // Add the line path
            chartArea
                .append("path")
                .datum(source.data)
                .attr("fill", "none")
                .attr("stroke", source.color)
                .attr("stroke-width", 1.5)
                .attr("d", line);

            // Add small dots at each data point
            chartArea
                .selectAll(`.dot-${source.id}`)
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

        // Add tooltip
        const tooltip = createTooltip(theme);

        // Add tooltip for data points
        sources.forEach((source) => {
            if (source.data.length === 0) return;

            chartArea
                .selectAll(`.data-point-${source.id}`)
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
                .on("mouseout", function (event: MouseEvent, d: any) {
                    d3.select(this).attr("r", 3).attr("fill", source.color);
                    tooltip.style("opacity", 0);
                });
        });

        return () => tooltip.remove();
    }, [
        frontendFramerate,
        backendFramerate,
        recentFrontendFrameDurations,
        recentBackendFrameDurations,
        frontendColor,
        backendColor,
        theme
    ]);

    return (
        <BaseD3ChartView
            title={title}
            renderChart={renderChart}
        />
    );
}
